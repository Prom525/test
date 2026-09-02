from __future__ import annotations

import inspect
import unittest
from collections import defaultdict

from app.main import app


# Bestaande technische schuld op baseline 2026-08-19.
#
# Waarde = maximaal momenteel toegestane multipliciteit.
#
# Als een duplicate wordt opgelost en nog maar 1x bestaat,
# blijft de test groen.
#
# Als een bestaande duplicate erger wordt of een nieuwe duplicate
# verschijnt, faalt de test.
KNOWN_DUPLICATES = {
    (
        "DELETE",
        "/analysis/rfq/{rfq_id}/positions/{position_id}",
    ): 3,
    (
        "GET",
        "/analysis/rfq/{rfq_id}/positions/{position_id}/datasheet/pdf",
    ): 2,
}


def collect_route_records():
    records = []

    for top_index, route in enumerate(app.routes):
        original_router = getattr(
            route,
            "original_router",
            None,
        )

        if original_router is not None:
            candidate_routes = original_router.routes
            wrapper_index = top_index
        else:
            candidate_routes = [route]
            wrapper_index = None

        for candidate in candidate_routes:
            path = getattr(candidate, "path", None)
            methods = getattr(candidate, "methods", None)

            if not path or not methods:
                continue

            endpoint = getattr(candidate, "endpoint", None)

            for method in sorted(methods):
                if method in {"HEAD", "OPTIONS"}:
                    continue

                records.append(
                    {
                        "method": method,
                        "path": path,
                        "module": getattr(
                            endpoint,
                            "__module__",
                            None,
                        ),
                        "name": getattr(
                            endpoint,
                            "__name__",
                            None,
                        ),
                        "wrapper_index": wrapper_index,
                    }
                )

    return records


def group_routes(records):
    grouped = defaultdict(list)

    for record in records:
        key = (
            record["method"],
            record["path"],
        )

        grouped[key].append(record)

    return grouped


class RouteUniquenessTests(unittest.TestCase):

    def test_no_unexpected_method_path_duplicates(self):
        grouped = group_routes(
            collect_route_records()
        )

        unexpected = {}

        for key, records in grouped.items():
            count = len(records)

            if count <= 1:
                continue

            allowed_max = KNOWN_DUPLICATES.get(key)

            if allowed_max is None:
                unexpected[key] = records
                continue

            if count > allowed_max:
                unexpected[key] = records

        if unexpected:
            lines = [
                "Onverwachte FastAPI METHOD+PATH duplicates:"
            ]

            for key, records in sorted(unexpected.items()):
                method, path = key

                lines.append(
                    f"{method} {path} count={len(records)}"
                )

                for record in records:
                    lines.append(
                        "  "
                        + f"{record['module']}."
                        + f"{record['name']}"
                        + f" wrapper={record['wrapper_index']}"
                    )

            self.fail("\n".join(lines))

    def test_analysis_assistant_is_registered_once(self):
        grouped = group_routes(
            collect_route_records()
        )

        key = (
            "POST",
            "/analysis/assistant/ask",
        )

        records = grouped.get(key, [])

        self.assertEqual(
            len(records),
            1,
            "POST /analysis/assistant/ask moet exact ??n keer bestaan.",
        )

        self.assertEqual(
            records[0]["module"],
            "app.routers.analysis_api_v10",
            (
                "De canonieke analysis assistant-route moet "
                "uit analysis_api_v10 komen."
            ),
        )

    def test_rfq_artifacts_is_registered_once_with_request_contract(self):
        matches = []

        for wrapper in app.routes:
            router = getattr(
                wrapper,
                "original_router",
                None,
            )

            if router is None:
                continue

            for child in router.routes:
                if (
                    getattr(child, "path", None)
                    == "/analysis/rfq/{rfq_id}/artifacts"
                    and "GET"
                    in (
                        getattr(child, "methods", None)
                        or set()
                    )
                ):
                    matches.append(
                        getattr(child, "endpoint", None)
                    )

        self.assertEqual(
            len(matches),
            1,
            (
                "GET /analysis/rfq/{rfq_id}/artifacts "
                "moet exact ??n keer bestaan."
            ),
        )

        signature = inspect.signature(matches[0])

        self.assertIn(
            "request",
            signature.parameters,
            (
                "De canonieke RFQ artifacts-route moet "
                "het bestaande Request-gebaseerde "
                "responsecontract behouden."
            ),
        )

    def test_orchestrator_ask_is_registered_once(self):
        grouped = group_routes(
            collect_route_records()
        )

        key = (
            "POST",
            "/orchestrator/ask",
        )

        self.assertEqual(
            len(grouped.get(key, [])),
            1,
            "POST /orchestrator/ask moet exact één keer bestaan.",
        )

    def test_current_known_duplicate_limits(self):
        grouped = group_routes(
            collect_route_records()
        )

        for key, maximum in KNOWN_DUPLICATES.items():
            actual = len(
                grouped.get(key, [])
            )

            self.assertLessEqual(
                actual,
                maximum,
                (
                    f"{key[0]} {key[1]} heeft "
                    f"{actual} registraties; "
                    f"baseline maximum is {maximum}."
                ),
            )


if __name__ == "__main__":
    unittest.main()