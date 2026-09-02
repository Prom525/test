import json
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orchestrator.complexity import assess_research_requirement
from app.orchestrator.research import run_bounded_research
from app.orchestrator.research_runtime import run_bounded_research_agent
from app.orchestrator.executor import Sender, execute_plan
from app.orchestrator.evidence_adapters import (
    normalize_execution_result_evidence,
)
from app.orchestrator.evidence_assessor import assess_evidence
from app.orchestrator.evidence_reconciler import reconcile_evidence
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
)
from app.orchestrator.evidence_research_executor import (
    execute_bounded_research,
)
from app.orchestrator.evidence_research_gate import (
    decide_research_requirement,
)
from app.orchestrator.evidence_synthesizer import (
    synthesize_grounded_evidence,
)
from app.orchestrator.models import OrchestratorAskRequest
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.understanding import understand_query
from app.text_encoding import repair_mojibake_text
# PROMATI_COMPACT_PUBLIC_RESULTS_V1
from app.orchestrator.public_results import compact_results_for_public_response
# PROMATI_TYPED_SERVICE_STATUS_CONSUMER_V1
from app.orchestrator.execution_status import has_service_accepted_execution




# PROMATI_ORCHESTRATOR_OBSERVABILITY_V1
ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION = (
    "promati.orchestrator.observability.v1"
)


def _observability_now() -> float:
    return time.perf_counter()


def _observability_elapsed_ms(
    started: float,
) -> int:
    elapsed = (
        _observability_now()
        - started
    )

    return max(
        0,
        int(
            round(
                elapsed * 1000
            )
        ),
    )


def _observability_call(
    timings: dict[str, int],
    key: str,
    callable_,
    *args,
    **kwargs,
):
    started = _observability_now()

    try:
        return callable_(
            *args,
            **kwargs,
        )
    finally:
        timings[key] = (
            _observability_elapsed_ms(
                started
            )
        )


def _observability_get(
    value: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(
        value,
        dict,
    ):
        return value.get(
            key,
            default,
        )

    return getattr(
        value,
        key,
        default,
    )


def _observability_nonnegative_int(
    value: Any,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        return 0

    try:
        number = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        0,
        number,
    )


def _new_observability_timings() -> dict[str, int]:
    return {
        "understanding": 0,
        "research_requirement": 0,
        "planning": 0,
        "initial_specialist": 0,
        "evidence_requirement_lookup": 0,
        "evidence_normalization": 0,
        "evidence_assessment": 0,
        "evidence_research_gate": 0,
        "evidence_research": 0,
        "reconciliation": 0,
        "synthesis": 0,
        "plan_research": 0,
        "presentation": 0,
        "response_build": 0,
        "total": 0,
    }


def _new_observability_counts() -> dict[str, int]:
    return {
        "execution_attempts": 0,
        "initial_specialist_calls": 0,
        "phase_c_research_follow_up_specialist_calls": 0,
        "plan_research_follow_up_specialist_calls": 0,
        "research_follow_up_specialist_calls": 0,
        "total_specialist_calls": 0,
        "initial_raw_result_rows": 0,
        "initial_evidence_items": 0,
        "reconciled_evidence_items": 0,
        "phase_c_ai_calls": 0,
        "plan_research_ai_calls": 0,
        "total_ai_calls": 0,
    }


# PROMATI_RESEARCH_AGENT_SERVICE_GATE_6B3
def _research_agent_enabled() -> bool:
    raw = os.getenv(
        "AI_RESEARCH_AGENT_ENABLED",
        "false",
    )
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

def _model_to_dict(model) -> dict[str, Any]:
    """
    Compatibel met Pydantic v1 en v2.
    Geeft JSON-veilige waarden terug, dus ook Enum -> string.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    return json.loads(model.json())



def _evidence_pipeline_to_dict(value: Any) -> Any:
    """Return a detached, JSON-safe representation."""
    if is_dataclass(value):
        return _evidence_pipeline_to_dict(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): _evidence_pipeline_to_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]

    if isinstance(value, (set, frozenset)):
        converted_items = [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]
        return sorted(
            converted_items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        )

    if isinstance(value, datetime):
        return value.isoformat()

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return None




# PROMATI_COMPACT_PUBLIC_EVIDENCE_PIPELINE_V1
def _compact_evidence_pipeline_for_public_response(
    pipeline: Any,
) -> Any:
    """
    Projecteer de interne Phase-C evidence pipeline naar een
    compacte publieke response.

    De interne objecten worden niet gewijzigd.
    Grote raw resultsets, evidence-items en claims blijven
    uitsluitend beschikbaar in het volledige debugprofiel.
    """
    if pipeline is None:
        return None

    if not isinstance(
        pipeline,
        dict,
    ):
        return None

    def _list_value(
        value: Any,
    ) -> list[Any]:
        if isinstance(
            value,
            (list, tuple),
        ):
            return list(value)

        return []

    def _dict_value(
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    def _compact_assessment(
        value: Any,
    ) -> dict[str, Any]:
        assessment = _dict_value(
            value
        )

        requirement_results = (
            _list_value(
                assessment.get(
                    "requirement_results"
                )
            )
        )

        compact_requirements: list[
            dict[str, Any]
        ] = []

        matched_ids: set[str] = set()

        for raw_requirement in (
            requirement_results
        ):
            if not isinstance(
                raw_requirement,
                dict,
            ):
                continue

            raw_ids = _list_value(
                raw_requirement.get(
                    "matched_evidence_ids"
                )
            )

            ids = [
                str(item)
                for item in raw_ids
                if item is not None
            ]

            matched_ids.update(
                ids
            )

            compact_requirements.append(
                {
                    "requirement_id": (
                        raw_requirement.get(
                            "requirement_id"
                        )
                    ),
                    "necessity": (
                        raw_requirement.get(
                            "necessity"
                        )
                    ),
                    "status": (
                        raw_requirement.get(
                            "status"
                        )
                    ),
                    "matched_evidence_count": (
                        len(ids)
                    ),
                    "present": (
                        raw_requirement.get(
                            "present"
                        )
                    ),
                    "relevant": (
                        raw_requirement.get(
                            "relevant"
                        )
                    ),
                    "grounded": (
                        raw_requirement.get(
                            "grounded"
                        )
                    ),
                    "fresh": (
                        raw_requirement.get(
                            "fresh"
                        )
                    ),
                    "conflicting": (
                        raw_requirement.get(
                            "conflicting"
                        )
                    ),
                    "reasons": (
                        _list_value(
                            raw_requirement.get(
                                "reasons"
                            )
                        )
                    ),
                }
            )

        return {
            "status": assessment.get(
                "status"
            ),
            "missing_required_requirement_ids": (
                _list_value(
                    assessment.get(
                        "missing_required_requirement_ids"
                    )
                )
            ),
            "conflicting_requirement_ids": (
                _list_value(
                    assessment.get(
                        "conflicting_requirement_ids"
                    )
                )
            ),
            "evidence_item_count": (
                len(matched_ids)
            ),
            "requirement_results": (
                compact_requirements
            ),
        }

    def _collect_evidence_ids(
        value: Any,
        result: set[str],
    ) -> None:
        if isinstance(
            value,
            dict,
        ):
            for key, item in value.items():
                key_text = str(
                    key
                ).casefold()

                if (
                    key_text.endswith(
                        "evidence_id"
                    )
                    and isinstance(
                        item,
                        str,
                    )
                ):
                    result.add(
                        item
                    )

                elif (
                    key_text.endswith(
                        "evidence_ids"
                    )
                    and isinstance(
                        item,
                        (list, tuple),
                    )
                ):
                    for evidence_id in item:
                        if isinstance(
                            evidence_id,
                            str,
                        ):
                            result.add(
                                evidence_id
                            )

                _collect_evidence_ids(
                    item,
                    result,
                )

        elif isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                _collect_evidence_ids(
                    item,
                    result,
                )

    initial_assessment = (
        _compact_assessment(
            pipeline.get(
                "initial_assessment"
            )
        )
    )

    research_decision = _dict_value(
        pipeline.get(
            "research_decision"
        )
    )

    research_execution = _dict_value(
        pipeline.get(
            "research_execution"
        )
    )

    reconciliation = _dict_value(
        pipeline.get(
            "reconciliation"
        )
    )

    synthesis = _dict_value(
        pipeline.get(
            "synthesis"
        )
    )

    initial_results = _list_value(
        research_execution.get(
            "initial_results"
        )
    )

    combined_results = _list_value(
        research_execution.get(
            "combined_results"
        )
    )

    initial_evidence = _list_value(
        reconciliation.get(
            "initial_evidence_items"
        )
    )

    reconciled_evidence = _list_value(
        reconciliation.get(
            "reconciled_evidence_items"
        )
    )

    claims = _list_value(
        synthesis.get(
            "claims"
        )
    )

    evidence_ids_used: set[str] = set()

    _collect_evidence_ids(
        claims,
        evidence_ids_used,
    )

    compact_reconciled_assessment = (
        _compact_assessment(
            reconciliation.get(
                "reconciled_assessment"
            )
        )
    )

    return {
        "profile": "compact_public_v1",
        "requirement_set_id": (
            pipeline.get(
                "requirement_set_id"
            )
        ),
        "initial_assessment": (
            initial_assessment
        ),
        "research_decision": {
            "status": (
                research_decision.get(
                    "status"
                )
            ),
            "research_required": (
                research_decision.get(
                    "research_required"
                )
            ),
            "target_requirement_ids": (
                _list_value(
                    research_decision.get(
                        "target_requirement_ids"
                    )
                )
            ),
            "reasons": (
                _list_value(
                    research_decision.get(
                        "reasons"
                    )
                )
            ),
        },
        "research_execution": {
            "status": (
                research_execution.get(
                    "status"
                )
            ),
            "research_performed": (
                research_execution.get(
                    "research_performed"
                )
            ),
            "target_requirement_ids": (
                _list_value(
                    research_execution.get(
                        "target_requirement_ids"
                    )
                )
            ),
            "initial_result_count": (
                len(initial_results)
            ),
            "combined_result_count": (
                len(combined_results)
            ),
            "blocked_reason": (
                research_execution.get(
                    "blocked_reason"
                )
            ),
        },
        "reconciliation": {
            "status": (
                reconciliation.get(
                    "status"
                )
            ),
            "research_status": (
                reconciliation.get(
                    "research_status"
                )
            ),
            "initial_evidence_count": (
                len(initial_evidence)
            ),
            "reconciled_evidence_count": (
                len(reconciled_evidence)
            ),
            "added_evidence_ids": (
                _list_value(
                    reconciliation.get(
                        "added_evidence_ids"
                    )
                )
            ),
            "discarded_result_count": (
                reconciliation.get(
                    "discarded_result_count"
                )
            ),
            "reasons": (
                _list_value(
                    reconciliation.get(
                        "reasons"
                    )
                )
            ),
            "reconciled_assessment_status": (
                compact_reconciled_assessment.get(
                    "status"
                )
            ),
        },
        "synthesis": {
            "status": (
                synthesis.get(
                    "status"
                )
            ),
            "claim_count": len(
                claims
            ),
            "evidence_ids_used": sorted(
                evidence_ids_used
            ),
            "warnings": (
                _list_value(
                    synthesis.get(
                        "warnings"
                    )
                )
            ),
        },
    }


def _display_name_code(
    name: Any,
    code: Any,
) -> str:
    name_text = (
        str(name).strip()
        if name is not None
        else ""
    )
    code_text = (
        str(code).strip()
        if code is not None
        else ""
    )

    if name_text and code_text:
        if name_text.upper() == code_text.upper():
            return name_text

        return f"{name_text} ({code_text})"

    if name_text:
        return name_text

    if code_text:
        return code_text

    return "onbekend"


def _format_quantity(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def _build_product_article_lines(
    specialist_result: dict[str, Any],
    *,
    include_inventory: bool,
    include_price: bool,
) -> list[str]:
    """
    Bouwt brongebonden artikelinformatie uit config_options.

    Er worden geen voorraad- of prijswaarden uit RAG afgeleid.
    Alleen concrete specialistvelden worden gepresenteerd.
    """
    config_options = specialist_result.get("config_options")

    if not isinstance(config_options, dict):
        return []

    rows = config_options.get("results")

    if not isinstance(rows, list) or not rows:
        return []

    lines = ["Actuele artikelinformatie:"]
    seen: set[str] = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        internal_ref = str(row.get("internal_ref") or "").strip()
        product_name = str(row.get("product_name") or "").strip()
        option_value = str(row.get("option_value") or "").strip()
        component_group = str(row.get("component_group") or "").strip()

        dedupe_key = internal_ref or "|".join(
            [product_name, option_value, component_group]
        )

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)

        details: list[str] = []

        if include_inventory:
            available_qty = row.get("available_qty")
            expected_qty = row.get("expected_qty")
            uom = str(row.get("uom") or "stuks").strip()

            if available_qty is not None:
                details.append(
                    "voorraad: "
                    f"{_format_quantity(available_qty)} {uom}"
                )

            if (
                isinstance(expected_qty, (int, float))
                and not isinstance(expected_qty, bool)
                and expected_qty > 0
            ):
                details.append(
                    "verwacht: "
                    f"{_format_quantity(expected_qty)} {uom}"
                )

        if include_price:
            sale_price = row.get("sale_price")

            if sale_price is not None:
                details.append(
                    "verkoopprijs: "
                    f"{_format_quantity(sale_price)}"
                )

        if not details:
            continue

        label = product_name or internal_ref or option_value or component_group

        if internal_ref and internal_ref not in label:
            label = f"{label} ({internal_ref})"

        lines.append(
            f"- {label}: " + "; ".join(details)
        )

    if len(lines) == 1:
        return []

    return lines

def _build_user_answer(
    results: list[dict[str, Any]],
    requested_information: list[str] | None = None,
) -> str | None:
    """
    Bouwt een user-facing presentatielaag boven specialistresultaten.

    Bronnen blijven gescheiden:
    - asset_context is leidend voor asset-identiteit;
    - product family_context is leidend voor productkennis;
    - ORG gebruikt alleen gestructureerde ORG-resultaten;
    - technical gebruikt alleen specialistdata die werkelijk
      in het resultaat aanwezig is;
    - ruwe specialistdata wordt nooit gewijzigd.
    """
    requested = {
        str(item).strip().casefold()
        for item in (requested_information or [])
        if str(item).strip()
    }

    # -----------------------------------------------------
    # 1. ASSET ANSWER
    # Bestaand gedrag houdt bewust de hoogste prioriteit.
    # -----------------------------------------------------

    asset_result = None
    asset_action = None

    for item in results:
        specialist_result = item.get("result")

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        if isinstance(
            specialist_result.get(
                "asset_resolution"
            ),
            dict,
        ):
            asset_result = specialist_result
            asset_action = str(
                item.get("action") or ""
            )
            break

    if asset_result is not None:
        context = asset_result.get(
            "asset_context"
        )

        if not isinstance(context, dict):
            context = {}

        entities = asset_result.get("entities")

        if not isinstance(entities, dict):
            entities = {}

        customer = (
            context.get("customer_code")
            or "onbekend"
        )

        site = (
            context.get("site_code")
            or "onbekend"
        )

        area = _display_name_code(
            context.get("area_name"),
            context.get("area_code"),
        )

        installation = _display_name_code(
            context.get("installation_name"),
            context.get("installation_code"),
        )

        band = (
            context.get("band_code_display")
            or context.get("band_code_norm")
            or entities.get("band_code")
            or "onbekend"
        )

        result_text = (
            asset_result.get("message")
            or asset_result.get("kort_resultaat")
        )

        answer_lines = [
            f"Klant: {customer}",
            f"Plaats: {site}",
            f"Gebied: {area}",
            f"Installatie: {installation}",
            f"Bandnummer: {band}",
        ]

        # PROMATI_INSPECTION_LATEST_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor inspection_latest.
        # Geen wijziging aan C7 answer ownership.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "inspection_summary"
        ):
            raw_rows = asset_result.get("resultaat")

            if isinstance(raw_rows, list):
                dated_rows: list[tuple[str, dict[str, Any]]] = []

                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        continue

                    document_date = str(
                        raw_row.get("document_date") or ""
                    ).strip()

                    if not document_date:
                        continue

                    dated_rows.append(
                        (
                            document_date,
                            raw_row,
                        )
                    )

                if dated_rows:
                    latest_date = max(
                        document_date
                        for document_date, _ in dated_rows
                    )

                    latest_rows = [
                        row
                        for document_date, row in dated_rows
                        if document_date == latest_date
                    ]

                    seen_measurements: set[
                        tuple[
                            str,
                            str,
                            str,
                            str,
                        ]
                    ] = set()

                    measurements: list[
                        dict[str, Any]
                    ] = []

                    for row in latest_rows:
                        meshoogte = row.get(
                            "meshoogte_mm"
                        )

                        if meshoogte is None:
                            continue

                        inspection_key = str(
                            row.get(
                                "inspection_key"
                            )
                            or ""
                        ).strip()

                        scraper_type = str(
                            row.get(
                                "scraper_type_raw"
                            )
                            or ""
                        ).strip()

                        location = str(
                            row.get("locatie_raw")
                            or ""
                        ).strip()

                        dedupe_key = (
                            inspection_key,
                            scraper_type,
                            location,
                            str(meshoogte),
                        )

                        if dedupe_key in seen_measurements:
                            continue

                        seen_measurements.add(
                            dedupe_key
                        )

                        measurements.append(
                            {
                                "inspection_key": (
                                    inspection_key
                                ),
                                "scraper_type": (
                                    scraper_type
                                ),
                                "location": location,
                                "meshoogte_mm": meshoogte,
                                "mes_vervangen": row.get(
                                    "mes_vervangen"
                                ),
                            }
                        )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Laatste inspectie: "
                                f"{latest_date}"
                            ),
                        ]
                    )

                    if measurements:
                        answer_lines.extend(
                            [
                                "",
                                "Schrapers:",
                            ]
                        )

                        for measurement in sorted(
                            measurements,
                            key=lambda item: (
                                item[
                                    "scraper_type"
                                ],
                                item[
                                    "location"
                                ],
                            ),
                        ):
                            scraper_type = (
                                measurement[
                                    "scraper_type"
                                ]
                                or "Onbekende schraper"
                            )

                            location = measurement[
                                "location"
                            ]

                            meshoogte = measurement[
                                "meshoogte_mm"
                            ]

                            label = scraper_type

                            if location:
                                label += (
                                    f" — {location}"
                                )

                            answer_lines.append(
                                f"- {label}: "
                                f"{meshoogte} mm"
                            )

                        replacement_values = [
                            item.get(
                                "mes_vervangen"
                            )
                            for item in measurements
                        ]

                        if (
                            replacement_values
                            and all(
                                value is False
                                for value
                                in replacement_values
                            )
                        ):
                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Geen mesvervanging "
                                        "geregistreerd bij "
                                        "deze laatste "
                                        "metingen."
                                    ),
                                ]
                            )

                    return "\n".join(
                        answer_lines
                    )

        # PROMATI_INSPECTION_TREND_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor inspection_trend.
        # Geen forecast en geen wijziging aan C7 answer ownership.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "lifecycle"
        ):
            raw_rows = asset_result.get("resultaat")

            if isinstance(raw_rows, list):
                groups: dict[
                    tuple[str, str, str],
                    dict[str, Any],
                ] = {}

                seen_measurements: set[
                    tuple[
                        str,
                        str,
                        str,
                        str,
                        str,
                        str,
                    ]
                ] = set()

                replacement_dates: set[str] = set()

                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        continue

                    inspected_on = str(
                        raw_row.get("inspected_on")
                        or ""
                    ).strip()

                    scraper_type = str(
                        raw_row.get(
                            "scraper_type_norm"
                        )
                        or ""
                    ).strip()

                    position_hint = str(
                        raw_row.get(
                            "position_hint"
                        )
                        or ""
                    ).strip()

                    cycle_raw = raw_row.get(
                        "cycle_id"
                    )

                    cycle_id = (
                        str(cycle_raw)
                        if cycle_raw is not None
                        else ""
                    )

                    canonical_key = str(
                        raw_row.get(
                            "canonical_inspection_key"
                        )
                        or ""
                    ).strip()

                    if (
                        raw_row.get("replace_event")
                        is True
                        and inspected_on
                    ):
                        replacement_dates.add(
                            inspected_on
                        )

                    meshoogte = raw_row.get(
                        "meshoogte_mm"
                    )

                    numeric_height = (
                        isinstance(
                            meshoogte,
                            (int, float),
                        )
                        and not isinstance(
                            meshoogte,
                            bool,
                        )
                    )

                    if not (
                        inspected_on
                        and scraper_type
                        and numeric_height
                    ):
                        continue

                    dedupe_key = (
                        canonical_key,
                        scraper_type,
                        position_hint,
                        cycle_id,
                        inspected_on,
                        str(meshoogte),
                    )

                    if dedupe_key in seen_measurements:
                        continue

                    seen_measurements.add(
                        dedupe_key
                    )

                    group_key = (
                        scraper_type,
                        position_hint,
                        cycle_id,
                    )

                    group = groups.setdefault(
                        group_key,
                        {
                            "scraper_type": scraper_type,
                            "position_hint": position_hint,
                            "cycle_id": cycle_id,
                            "points": [],
                        },
                    )

                    group["points"].append(
                        (
                            inspected_on,
                            float(meshoogte),
                        )
                    )

                usable_groups: list[
                    dict[str, Any]
                ] = []

                total_measurements = 0

                for group in groups.values():
                    points = sorted(
                        group["points"],
                        key=lambda item: item[0],
                    )

                    if not points:
                        continue

                    group["points"] = points
                    total_measurements += len(points)
                    usable_groups.append(group)

                if usable_groups:
                    usable_groups.sort(
                        key=lambda group: (
                            group["points"][-1][0],
                            group["scraper_type"],
                            group["position_hint"],
                            group["cycle_id"],
                        ),
                        reverse=True,
                    )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Trendgegevens: "
                                f"{total_measurements} metingen "
                                f"verdeeld over "
                                f"{len(usable_groups)} cycli."
                            ),
                            "",
                            "Historie per schraper/cyclus:",
                        ]
                    )

                    def _format_mm(
                        value: float,
                    ) -> str:
                        if value.is_integer():
                            return str(int(value))

                        return (
                            f"{value:.2f}"
                            .rstrip("0")
                            .rstrip(".")
                        )

                    for group in usable_groups:
                        points = group["points"]

                        first_date, first_height = (
                            points[0]
                        )

                        last_date, last_height = (
                            points[-1]
                        )

                        label_parts = [
                            group["scraper_type"]
                        ]

                        if group["position_hint"]:
                            label_parts.append(
                                group["position_hint"]
                            )

                        if group["cycle_id"]:
                            label_parts.append(
                                (
                                    "cyclus "
                                    f"{group['cycle_id']}"
                                )
                            )

                        label = " — ".join(
                            label_parts
                        )

                        if len(points) == 1:
                            detail = (
                                f"1 meting, "
                                f"{last_date} "
                                f"{_format_mm(last_height)} mm"
                            )
                        else:
                            detail = (
                                f"{len(points)} metingen, "
                                f"{first_date} "
                                f"{_format_mm(first_height)} mm "
                                f"→ "
                                f"{last_date} "
                                f"{_format_mm(last_height)} mm"
                            )

                        answer_lines.append(
                            f"- {label}: {detail}"
                        )

                    # PROMATI_INSPECTION_TREND_FACET_PRESENTATION_V1
                    #
                    # P1.1b blijft presentation-only.
                    # De lifecyclebron wordt niet opgewaardeerd
                    # tot actuele onderhouds- of forecastbron.
                    if (
                        "latest_measurements"
                        in requested
                    ):
                        latest_by_position: dict[
                            tuple[str, str],
                            dict[str, Any],
                        ] = {}

                        for group in usable_groups:
                            points = group["points"]

                            if not points:
                                continue

                            (
                                latest_date,
                                latest_height,
                            ) = points[-1]

                            latest_key = (
                                group["scraper_type"],
                                group["position_hint"],
                            )

                            existing = (
                                latest_by_position.get(
                                    latest_key
                                )
                            )

                            if (
                                existing is None
                                or latest_date
                                > existing["inspected_on"]
                            ):
                                latest_by_position[
                                    latest_key
                                ] = {
                                    "scraper_type": (
                                        group[
                                            "scraper_type"
                                        ]
                                    ),
                                    "position_hint": (
                                        group[
                                            "position_hint"
                                        ]
                                    ),
                                    "inspected_on": (
                                        latest_date
                                    ),
                                    "meshoogte_mm": (
                                        latest_height
                                    ),
                                }

                        if latest_by_position:
                            latest_rows = sorted(
                                latest_by_position.values(),
                                key=lambda item: (
                                    item["inspected_on"],
                                    item["scraper_type"],
                                    item["position_hint"],
                                ),
                                reverse=True,
                            )

                            answer_lines.extend(
                                [
                                    "",
                                    (
                                        "Laatste lifecycle-meting "
                                        "per schraper/positie:"
                                    ),
                                ]
                            )

                            for measurement in latest_rows:
                                label = measurement[
                                    "scraper_type"
                                ]

                                if measurement[
                                    "position_hint"
                                ]:
                                    label = (
                                        label
                                        + " - "
                                        + measurement[
                                            "position_hint"
                                        ]
                                    )

                                height_text = _format_mm(
                                    measurement[
                                        "meshoogte_mm"
                                    ]
                                )

                                date_text = str(
                                    measurement[
                                        "inspected_on"
                                    ]
                                )

                                answer_lines.append(
                                    (
                                        "- "
                                        + label
                                        + ": "
                                        + height_text
                                        + " mm op "
                                        + date_text
                                    )
                                )

                    if replacement_dates:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Geregistreerde "
                                    "vervangevents: "
                                    + ", ".join(
                                        sorted(
                                            replacement_dates
                                        )
                                    )
                                ),
                            ]
                        )

                    elif (
                        "replacement_events"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Geregistreerde "
                                    "vervangevents: geen "
                                    "in deze lifecyclebron."
                                ),
                            ]
                        )

                    if (
                        "replacement_advice"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Vervangadvies: niet bepaald "
                                    "uit deze lifecyclehistorie; "
                                    "hiervoor is een actuele "
                                    "onderhouds-/forecastanalyse "
                                    "nodig."
                                ),
                            ]
                        )

                    if (
                        "uncertainties"
                        in requested
                    ):
                        answer_lines.extend(
                            [
                                "",
                                "Onzekerheden:",
                                (
                                    "- De weergegeven laatste "
                                    "meshoogte is de meest recente "
                                    "lifecycle-meting per "
                                    "schraper/positie in deze bron; "
                                    "dit bevestigt niet dat de "
                                    "positie nog actueel actief is."
                                ),
                                (
                                    "- Deze lifecyclebron bevat "
                                    "geen afzonderlijke actuele "
                                    "vervang-/forecastanalyse; "
                                    "daarom wordt hier geen "
                                    "vervangmoment afgeleid."
                                ),
                            ]
                        )

                    return "\n".join(
                        answer_lines
                    )

        # PROMATI_MAINTENANCE_PRIORITY_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor maintenance_priority.
        # Geen wijziging aan C7 answer ownership.
        # 3 mm blijft vervanggrens; 6 mm is alleen prestatiegrens.
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "maintenance_positions"
        ):
            raw_rows = asset_result.get(
                "resultaat"
            )

            if isinstance(
                raw_rows,
                list,
            ):
                positions: list[
                    dict[str, Any]
                ] = []

                seen_positions: set[
                    tuple[
                        str,
                        str,
                        str,
                        str,
                    ]
                ] = set()

                for raw_row in raw_rows:
                    if not isinstance(
                        raw_row,
                        dict,
                    ):
                        continue

                    scraper_types = str(
                        raw_row.get(
                            "scraper_types_clean"
                        )
                        or raw_row.get(
                            "scraper_types"
                        )
                        or ""
                    ).strip()

                    position_hint = str(
                        raw_row.get(
                            "position_hint"
                        )
                        or ""
                    ).strip()

                    cycle_end = str(
                        raw_row.get(
                            "cycle_end"
                        )
                        or ""
                    ).strip()

                    priority_raw = (
                        raw_row.get(
                            "prioriteit"
                        )
                    )

                    priority = (
                        float(priority_raw)
                        if (
                            isinstance(
                                priority_raw,
                                (int, float),
                            )
                            and not isinstance(
                                priority_raw,
                                bool,
                            )
                        )
                        else float("inf")
                    )

                    dedupe_key = (
                        scraper_types,
                        position_hint,
                        cycle_end,
                        str(priority_raw),
                    )

                    if (
                        dedupe_key
                        in seen_positions
                    ):
                        continue

                    seen_positions.add(
                        dedupe_key
                    )

                    end_height_raw = (
                        raw_row.get(
                            "eind_meshoogte_mm"
                        )
                    )

                    numeric_end_height = (
                        isinstance(
                            end_height_raw,
                            (int, float),
                        )
                        and not isinstance(
                            end_height_raw,
                            bool,
                        )
                    )

                    end_height = (
                        float(end_height_raw)
                        if numeric_end_height
                        else None
                    )

                    meetpunten_raw = (
                        raw_row.get(
                            "meetpunten"
                        )
                    )

                    usable_point_count = (
                        isinstance(
                            meetpunten_raw,
                            int,
                        )
                        and not isinstance(
                            meetpunten_raw,
                            bool,
                        )
                        and meetpunten_raw
                        >= 3
                    )

                    forecast_date = str(
                        raw_row.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        or ""
                    ).strip()

                    performance_action = str(
                        raw_row.get(
                            "prestatie_vervangmoment"
                        )
                        or ""
                    ).strip()

                    status_6mm = str(
                        raw_row.get(
                            "status_6mm"
                        )
                        or ""
                    ).strip()

                    status_3mm = str(
                        raw_row.get(
                            "status_3mm"
                        )
                        or ""
                    ).strip()

                    if (
                        numeric_end_height
                        and end_height
                        is not None
                        and end_height <= 3.0
                    ):
                        action = (
                            "NU VERVANGEN"
                        )
                    elif (
                        performance_action
                        == (
                            "CONTROLEREN_"
                            "PRESTATIEGRENS"
                        )
                        or status_6mm
                        == "OP_OF_ONDER_6MM"
                    ):
                        action = (
                            "Prestatiegrens "
                            "controleren"
                        )
                    elif not (
                        numeric_end_height
                    ):
                        action = (
                            "Trend controleren; "
                            "geen bruikbare "
                            "actuele eindmeting"
                        )
                    elif (
                        status_3mm
                        == "CHECK_TREND"
                    ):
                        action = (
                            "Trend controleren"
                        )
                    else:
                        action = "Monitoren"

                    reliable_forecast = (
                        usable_point_count
                        and numeric_end_height
                        and forecast_date != ""
                    )

                    positions.append(
                        {
                            "priority": (
                                priority
                            ),
                            "priority_raw": (
                                priority_raw
                            ),
                            "scraper_types": (
                                scraper_types
                                or "Onbekende schraper"
                            ),
                            "position_hint": (
                                position_hint
                                or "positie onbekend"
                            ),
                            "cycle_end": (
                                cycle_end
                            ),
                            "meetpunten": (
                                meetpunten_raw
                            ),
                            "end_height": (
                                end_height
                            ),
                            "action": action,
                            "forecast_date": (
                                forecast_date
                            ),
                            "reliable_forecast": (
                                reliable_forecast
                            ),
                        }
                    )

                if positions:
                    positions.sort(
                        key=lambda item: (
                            item["priority"],
                            item[
                                "scraper_types"
                            ],
                            item[
                                "position_hint"
                            ],
                        )
                    )

                    def _format_mm(
                        value: float,
                    ) -> str:
                        if value.is_integer():
                            return str(
                                int(value)
                            )

                        return (
                            f"{value:.2f}"
                            .rstrip("0")
                            .rstrip(".")
                        )

                    answer_lines.extend(
                        [
                            "",
                            "Onderhoudsprioriteit:",
                        ]
                    )

                    for index, position in enumerate(
                        positions,
                        start=1,
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    f"{index}. "
                                    f"{position['scraper_types']}"
                                    " — "
                                    f"{position['position_hint']}"
                                ),
                            ]
                        )

                        end_height = (
                            position[
                                "end_height"
                            ]
                        )

                        cycle_end = (
                            position[
                                "cycle_end"
                            ]
                        )

                        if (
                            end_height
                            is not None
                        ):
                            measurement_line = (
                                "   Laatste gemeten "
                                "meshoogte: "
                                f"{_format_mm(end_height)} mm"
                            )

                            if cycle_end:
                                measurement_line += (
                                    f" op {cycle_end}"
                                )

                            answer_lines.append(
                                measurement_line
                            )
                        else:
                            answer_lines.append(
                                "   Laatste gemeten "
                                "meshoogte: "
                                "niet beschikbaar"
                            )

                        answer_lines.append(
                            "   Actie: "
                            f"{position['action']}"
                        )

                        if (
                            position[
                                "reliable_forecast"
                            ]
                        ):
                            answer_lines.append(
                                "   Prognose 3 mm: "
                                "rond "
                                f"{position['forecast_date']}"
                            )

                            answer_lines.append(
                                "   Onderbouwing: "
                                f"{position['meetpunten']} "
                                "meetpunten"
                            )
                        else:
                            answer_lines.append(
                                "   Geen betrouwbare "
                                "forecast beschikbaar"
                            )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Let op: 3 mm is de "
                                "vervanggrens. "
                                "De 6 mm-grens is een "
                                "prestatiecontrole en "
                                "betekent niet automatisch "
                                "vervangen."
                            ),
                        ]
                    )

                    return "\n".join(
                        answer_lines
                    )


        # PROMATI_REPLACEMENT_ADVICE_PRESENTATION_V1
        #
        # Smalle legacy-presentatie voor replacement_advice.
        # Geen wijziging aan C7 answer ownership.
        #
        # Semantiek:
        # - gemeten <= 3 mm => NU VERVANGEN
        # - VERVANGEN_VOORBEREIDEN blijft voorbereiden
        # - forecast alleen bij >= 3 bruikbare meetpunten
        # - geen relatieve dagen-tot-3mm presentatie
        if (
            asset_action == "analysis_assistant"
            and str(
                asset_result.get("intent") or ""
            )
            == "band_deep_analysis"
        ):
            raw_positions = asset_result.get(
                "gecombineerde_slijtage"
            )

            raw_forecasts = asset_result.get(
                "forecast_3mm"
            )

            if isinstance(
                raw_positions,
                list,
            ):
                if not isinstance(
                    raw_forecasts,
                    list,
                ):
                    raw_forecasts = []

                def _numeric(
                    value: Any,
                ) -> bool:
                    return (
                        isinstance(
                            value,
                            (int, float),
                        )
                        and not isinstance(
                            value,
                            bool,
                        )
                    )

                def _format_mm(
                    value: float,
                ) -> str:
                    if value.is_integer():
                        return str(
                            int(value)
                        )

                    return (
                        f"{value:.2f}"
                        .rstrip("0")
                        .rstrip(".")
                    )

                def _family_from_text(
                    value: Any,
                ) -> str:
                    text = str(
                        value or ""
                    ).strip().upper()

                    if not text:
                        return ""

                    first = text[0]

                    if first in {
                        "R",
                        "U",
                        "T",
                    }:
                        return first

                    return ""

                eligible_forecasts_by_family: dict[
                    str,
                    list[dict[str, Any]],
                ] = {}

                for raw_forecast in raw_forecasts:
                    if not isinstance(
                        raw_forecast,
                        dict,
                    ):
                        continue

                    meetpunten = raw_forecast.get(
                        "meetpunten"
                    )

                    end_height = raw_forecast.get(
                        "eind_meshoogte_mm"
                    )

                    wear_rate = raw_forecast.get(
                        "slijtage_mm_per_dag"
                    )

                    days_to_3mm = raw_forecast.get(
                        "geschatte_dagen_tot_3mm"
                    )

                    forecast_date = str(
                        raw_forecast.get(
                            "geschatte_vervangdatum_bij_3mm"
                        )
                        or ""
                    ).strip()

                    family = _family_from_text(
                        raw_forecast.get(
                            "scraper_type_norm"
                        )
                    )

                    eligible = (
                        isinstance(
                            meetpunten,
                            int,
                        )
                        and not isinstance(
                            meetpunten,
                            bool,
                        )
                        and meetpunten >= 3
                        and _numeric(
                            end_height
                        )
                        and _numeric(
                            wear_rate
                        )
                        and _numeric(
                            days_to_3mm
                        )
                        and forecast_date != ""
                        and family != ""
                    )

                    if not eligible:
                        continue

                    eligible_forecasts_by_family.setdefault(
                        family,
                        [],
                    ).append(
                        raw_forecast
                    )

                positions: list[
                    dict[str, Any]
                ] = []

                seen_positions: set[
                    tuple[
                        str,
                        str,
                        str,
                    ]
                ] = set()

                for raw_position in raw_positions:
                    if not isinstance(
                        raw_position,
                        dict,
                    ):
                        continue

                    scraper_type = str(
                        raw_position.get(
                            "scraper_type_norm"
                        )
                        or ""
                    ).strip()

                    family = str(
                        raw_position.get(
                            "scraper_family"
                        )
                        or ""
                    ).strip().upper()

                    if not family:
                        family = _family_from_text(
                            scraper_type
                        )

                    position_display = str(
                        raw_position.get(
                            "position_display"
                        )
                        or ""
                    ).strip()

                    inspection_date = str(
                        raw_position.get(
                            "laatste_inspectiedatum"
                        )
                        or ""
                    ).strip()

                    height_raw = (
                        raw_position.get(
                            "meshoogte_mm"
                        )
                    )

                    height = (
                        float(height_raw)
                        if _numeric(
                            height_raw
                        )
                        else None
                    )

                    advice = str(
                        raw_position.get(
                            "onderhoudsadvies_unified"
                        )
                        or ""
                    ).strip().upper()

                    dedupe_key = (
                        scraper_type,
                        position_display,
                        inspection_date,
                    )

                    if (
                        dedupe_key
                        in seen_positions
                    ):
                        continue

                    seen_positions.add(
                        dedupe_key
                    )

                    if (
                        height is not None
                        and height <= 3.0
                    ):
                        action = (
                            "NU VERVANGEN"
                        )

                        action_rank = 0

                    elif (
                        advice
                        == "VERVANGEN_VOORBEREIDEN"
                    ):
                        action = (
                            "Vervanging voorbereiden"
                        )

                        action_rank = 1

                    elif (
                        advice
                        == "CONTROLEREN_BIJ_STOP"
                    ):
                        action = (
                            "Controleren bij stop"
                        )

                        action_rank = 2

                    else:
                        action = "Monitoren"
                        action_rank = 3

                    forecast = None

                    family_forecasts = (
                        eligible_forecasts_by_family.get(
                            family,
                            [],
                        )
                    )

                    # Fail-closed:
                    # alleen koppelen wanneer precies
                    # één betrouwbare forecast bestaat
                    # voor deze scraperfamilie.
                    if (
                        len(
                            family_forecasts
                        )
                        == 1
                    ):
                        forecast = (
                            family_forecasts[0]
                        )

                    positions.append(
                        {
                            "scraper_type": (
                                scraper_type
                                or "Onbekende schraper"
                            ),
                            "position": (
                                position_display
                                or "positie onbekend"
                            ),
                            "inspection_date": (
                                inspection_date
                            ),
                            "height": height,
                            "action": action,
                            "action_rank": (
                                action_rank
                            ),
                            "forecast": (
                                forecast
                            ),
                        }
                    )

                if positions:
                    positions.sort(
                        key=lambda item: (
                            item["action_rank"],
                            item["scraper_type"],
                            item["position"],
                        )
                    )

                    answer_lines.extend(
                        [
                            "",
                            "Vervangadvies:",
                        ]
                    )

                    for index, position in enumerate(
                        positions,
                        start=1,
                    ):
                        answer_lines.extend(
                            [
                                "",
                                (
                                    f"{index}. "
                                    f"{position['scraper_type']}"
                                    " — "
                                    f"{position['position']}"
                                ),
                            ]
                        )

                        height = position[
                            "height"
                        ]

                        inspection_date = position[
                            "inspection_date"
                        ]

                        if height is not None:
                            measurement_line = (
                                "   Laatste gemeten "
                                "meshoogte: "
                                f"{_format_mm(height)} mm"
                            )

                            if inspection_date:
                                measurement_line += (
                                    f" op {inspection_date}"
                                )

                            answer_lines.append(
                                measurement_line
                            )

                        else:
                            answer_lines.append(
                                "   Laatste gemeten "
                                "meshoogte: "
                                "niet beschikbaar"
                            )

                        answer_lines.append(
                            "   Advies: "
                            f"{position['action']}"
                        )

                        forecast = position[
                            "forecast"
                        ]

                        if isinstance(
                            forecast,
                            dict,
                        ):
                            forecast_date = str(
                                forecast.get(
                                    "geschatte_vervangdatum_bij_3mm"
                                )
                                or ""
                            ).strip()

                            meetpunten = (
                                forecast.get(
                                    "meetpunten"
                                )
                            )

                            answer_lines.append(
                                "   Prognose 3 mm: "
                                f"rond {forecast_date}"
                            )

                            answer_lines.append(
                                "   Onderbouwing: "
                                f"{meetpunten} meetpunten"
                            )

                        else:
                            answer_lines.append(
                                "   Geen betrouwbare "
                                "forecast beschikbaar"
                            )

                    answer_lines.extend(
                        [
                            "",
                            (
                                "Let op: 3 mm is de "
                                "vervanggrens. "
                                "Een advies 'vervanging "
                                "voorbereiden' betekent "
                                "niet dat het mes nu al "
                                "de vervanggrens heeft "
                                "bereikt."
                            ),
                        ]
                    )

                    # PROMATI_REPLACEMENT_ADVICE_FACET_PRESENTATION_V1
                    #
                    # P1.2b: facetprojecties uit dezelfde
                    # band_deep_analysis-response.
                    #
                    # Actuele meshoogte en vervangadvies blijven
                    # uitsluitend gebaseerd op gecombineerde_slijtage
                    # en de bestaande forecastlogica hierboven.
                    # Lifecycle wordt alleen gebruikt voor historie
                    # en geregistreerde vervangevents.
                    facet_requested = bool(
                        {
                            "lifecycle_trend",
                            "replacement_events",
                            "uncertainties",
                        }
                        & requested
                    )

                    if facet_requested:
                        raw_lifecycle = (
                            asset_result.get(
                                "lifecycle"
                            )
                        )

                        lifecycle_available = (
                            isinstance(
                                raw_lifecycle,
                                list,
                            )
                        )

                        lifecycle_groups: dict[
                            tuple[str, str, str],
                            dict[str, Any],
                        ] = {}

                        lifecycle_replacement_dates: (
                            set[str]
                        ) = set()

                        seen_lifecycle_measurements: set[
                            tuple[
                                str,
                                str,
                                str,
                                str,
                                str,
                                str,
                            ]
                        ] = set()

                        if lifecycle_available:
                            for raw_row in raw_lifecycle:
                                if not isinstance(
                                    raw_row,
                                    dict,
                                ):
                                    continue

                                inspected_on = str(
                                    raw_row.get(
                                        "inspected_on"
                                    )
                                    or ""
                                ).strip()

                                scraper_type = str(
                                    raw_row.get(
                                        "scraper_type_norm"
                                    )
                                    or ""
                                ).strip()

                                position_hint = str(
                                    raw_row.get(
                                        "position_hint"
                                    )
                                    or ""
                                ).strip()

                                cycle_raw = raw_row.get(
                                    "cycle_id"
                                )

                                cycle_id = (
                                    str(cycle_raw)
                                    if cycle_raw
                                    is not None
                                    else ""
                                )

                                canonical_key = str(
                                    raw_row.get(
                                        "canonical_inspection_key"
                                    )
                                    or ""
                                ).strip()

                                if (
                                    raw_row.get(
                                        "replace_event"
                                    )
                                    is True
                                    and inspected_on
                                ):
                                    lifecycle_replacement_dates.add(
                                        inspected_on
                                    )

                                meshoogte = (
                                    raw_row.get(
                                        "meshoogte_mm"
                                    )
                                )

                                if not (
                                    inspected_on
                                    and scraper_type
                                    and _numeric(
                                        meshoogte
                                    )
                                ):
                                    continue

                                dedupe_key = (
                                    canonical_key,
                                    scraper_type,
                                    position_hint,
                                    cycle_id,
                                    inspected_on,
                                    str(meshoogte),
                                )

                                if (
                                    dedupe_key
                                    in seen_lifecycle_measurements
                                ):
                                    continue

                                seen_lifecycle_measurements.add(
                                    dedupe_key
                                )

                                group_key = (
                                    scraper_type,
                                    position_hint,
                                    cycle_id,
                                )

                                group = (
                                    lifecycle_groups.setdefault(
                                        group_key,
                                        {
                                            "scraper_type": (
                                                scraper_type
                                            ),
                                            "position_hint": (
                                                position_hint
                                            ),
                                            "cycle_id": (
                                                cycle_id
                                            ),
                                            "points": [],
                                        },
                                    )
                                )

                                group["points"].append(
                                    (
                                        inspected_on,
                                        float(
                                            meshoogte
                                        ),
                                    )
                                )

                        usable_lifecycle_groups: list[
                            dict[str, Any]
                        ] = []

                        lifecycle_measurement_count = 0

                        for group in (
                            lifecycle_groups.values()
                        ):
                            points = sorted(
                                group["points"],
                                key=lambda item: (
                                    item[0]
                                ),
                            )

                            if not points:
                                continue

                            group["points"] = points

                            lifecycle_measurement_count += (
                                len(points)
                            )

                            usable_lifecycle_groups.append(
                                group
                            )

                        usable_lifecycle_groups.sort(
                            key=lambda group: (
                                group["points"][-1][0],
                                group["scraper_type"],
                                group["position_hint"],
                                group["cycle_id"],
                            ),
                            reverse=True,
                        )

                        if (
                            "lifecycle_trend"
                            in requested
                        ):
                            if usable_lifecycle_groups:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Lifecycle-trend: "
                                            f"{lifecycle_measurement_count} "
                                            "metingen verdeeld over "
                                            f"{len(usable_lifecycle_groups)} "
                                            "cycli."
                                        ),
                                    ]
                                )

                                for group in (
                                    usable_lifecycle_groups
                                ):
                                    points = (
                                        group["points"]
                                    )

                                    (
                                        first_date,
                                        first_height,
                                    ) = points[0]

                                    (
                                        last_date,
                                        last_height,
                                    ) = points[-1]

                                    label_parts = [
                                        group[
                                            "scraper_type"
                                        ]
                                    ]

                                    if group[
                                        "position_hint"
                                    ]:
                                        label_parts.append(
                                            group[
                                                "position_hint"
                                            ]
                                        )

                                    if group[
                                        "cycle_id"
                                    ]:
                                        label_parts.append(
                                            (
                                                "cyclus "
                                                + group[
                                                    "cycle_id"
                                                ]
                                            )
                                        )

                                    label = (
                                        " - ".join(
                                            label_parts
                                        )
                                    )

                                    if len(points) == 1:
                                        detail = (
                                            "1 meting, "
                                            + last_date
                                            + " "
                                            + _format_mm(
                                                last_height
                                            )
                                            + " mm"
                                        )
                                    else:
                                        detail = (
                                            str(
                                                len(points)
                                            )
                                            + " metingen, "
                                            + first_date
                                            + " "
                                            + _format_mm(
                                                first_height
                                            )
                                            + " mm -> "
                                            + last_date
                                            + " "
                                            + _format_mm(
                                                last_height
                                            )
                                            + " mm"
                                        )

                                    answer_lines.append(
                                        (
                                            "- "
                                            + label
                                            + ": "
                                            + detail
                                        )
                                    )

                            else:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Lifecycle-trend: "
                                            "niet beschikbaar "
                                            "in deze "
                                            "deep-analysisbron."
                                        ),
                                    ]
                                )

                        if (
                            "replacement_events"
                            in requested
                        ):
                            if lifecycle_available:
                                if (
                                    lifecycle_replacement_dates
                                ):
                                    answer_lines.extend(
                                        [
                                            "",
                                            (
                                                "Geregistreerde "
                                                "vervangevents: "
                                                + ", ".join(
                                                    sorted(
                                                        lifecycle_replacement_dates
                                                    )
                                                )
                                            ),
                                        ]
                                    )
                                else:
                                    answer_lines.extend(
                                        [
                                            "",
                                            (
                                                "Geregistreerde "
                                                "vervangevents: "
                                                "geen geregistreerd "
                                                "in de lifecycle."
                                            ),
                                        ]
                                    )
                            else:
                                answer_lines.extend(
                                    [
                                        "",
                                        (
                                            "Geregistreerde "
                                            "vervangevents: "
                                            "niet beschikbaar "
                                            "in deze "
                                            "deep-analysisbron."
                                        ),
                                    ]
                                )

                        if (
                            "uncertainties"
                            in requested
                        ):
                            without_reliable_forecast = [
                                position
                                for position in positions
                                if not isinstance(
                                    position[
                                        "forecast"
                                    ],
                                    dict,
                                )
                            ]

                            answer_lines.extend(
                                [
                                    "",
                                    "Onzekerheden:",
                                ]
                            )

                            if (
                                without_reliable_forecast
                            ):
                                answer_lines.append(
                                    (
                                        "- Voor "
                                        f"{len(without_reliable_forecast)} "
                                        "van "
                                        f"{len(positions)} "
                                        "gepresenteerde posities "
                                        "is geen betrouwbare "
                                        "3 mm-forecast beschikbaar."
                                    )
                                )
                            else:
                                answer_lines.append(
                                    (
                                        "- Voor alle "
                                        "gepresenteerde posities "
                                        "is volgens de huidige "
                                        "forecastcriteria een "
                                        "3 mm-prognose beschikbaar."
                                    )
                                )

                            if lifecycle_available:
                                answer_lines.append(
                                    (
                                        "- Historische "
                                        "lifecycle-posities worden "
                                        "alleen gebruikt voor trend "
                                        "en vervangevents; actuele "
                                        "meshoogtes en vervangadvies "
                                        "hierboven worden daar niet "
                                        "uit afgeleid."
                                    )
                                )
                            else:
                                answer_lines.append(
                                    (
                                        "- Lifecyclehistorie "
                                        "ontbreekt in deze "
                                        "deep-analysisresponse."
                                    )
                                )

                    return "\n".join(
                        answer_lines
                    )

        if result_text:
            answer_lines.extend(
                [
                    "",
                    str(result_text),
                ]
            )

        return "\n".join(answer_lines)

    # -----------------------------------------------------
    # 2. NON-ASSET ANSWERS
    # -----------------------------------------------------

    for item in results:
        specialist_result = item.get("result")

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        action = str(
            item.get("action") or ""
        )

        context_type = str(
            specialist_result.get(
                "context_type"
            )
            or ""
        )

        # -------------------------------------------------
        # PROMATI_DIAGNOSTICS_PRESENTATION_V1
        # -------------------------------------------------

        if action == "diagnostics_assistant":
            status = str(
                specialist_result.get("status")
                or "unknown"
            )

            mode = str(
                specialist_result.get("mode")
                or "overview"
            )

            domain = str(
                specialist_result.get("domain")
                or "diagnostics"
            )

            summary = specialist_result.get(
                "summary"
            )

            if not isinstance(summary, dict):
                summary = {}

            findings = specialist_result.get(
                "findings"
            )

            if not isinstance(findings, list):
                findings = []

            recommended_actions = (
                specialist_result.get(
                    "recommended_actions"
                )
            )

            if not isinstance(
                recommended_actions,
                list,
            ):
                recommended_actions = []

            answer_lines = [
                (
                    f"Diagnose ({domain} / {mode}): "
                    f"{status}"
                )
            ]

            gpt_diagnosis = summary.get(
                "gpt_diagnosis"
            )

            if isinstance(gpt_diagnosis, dict):
                headline = gpt_diagnosis.get(
                    "headline"
                )

                if headline:
                    answer_lines.extend(
                        [
                            "",
                            str(headline),
                        ]
                    )

                interpretation = (
                    gpt_diagnosis.get(
                        "interpretation"
                    )
                )

                if isinstance(
                    interpretation,
                    list,
                ):
                    for line in interpretation[:8]:
                        if line:
                            answer_lines.append(
                                f"- {line}"
                            )

            elif summary.get("message"):
                answer_lines.extend(
                    [
                        "",
                        str(summary.get("message")),
                    ]
                )

            else:
                compact_fields = (
                    ("view_name", "View"),
                    ("object_name", "Object"),
                    ("row_count", "Rijen"),
                    (
                        "dependencies_found",
                        "Dependencies",
                    ),
                    (
                        "objects_checked",
                        "Objecten gecontroleerd",
                    ),
                    (
                        "comparisons_made",
                        "Vergelijkingen",
                    ),
                )

                compact_values = []

                for key, label in compact_fields:
                    value = summary.get(key)

                    if value is not None:
                        compact_values.append(
                            f"{label}: {value}"
                        )

                if compact_values:
                    answer_lines.extend(
                        [
                            "",
                            "; ".join(
                                compact_values
                            ),
                        ]
                    )

            if findings:
                answer_lines.extend(
                    [
                        "",
                        "Bevindingen:",
                    ]
                )

                for finding in findings[:8]:
                    if not isinstance(
                        finding,
                        dict,
                    ):
                        continue

                    severity = str(
                        finding.get("severity")
                        or "info"
                    ).upper()

                    issue = (
                        finding.get("issue")
                        or finding.get("message")
                    )

                    if issue:
                        answer_lines.append(
                            f"- [{severity}] {issue}"
                        )

            if recommended_actions:
                answer_lines.extend(
                    [
                        "",
                        "Aanbevolen vervolgstappen:",
                    ]
                )

                for action_text in (
                    recommended_actions[:5]
                ):
                    if action_text:
                        answer_lines.append(
                            f"- {action_text}"
                        )

            return "\n".join(answer_lines)

        # -------------------------------------------------
        # PROMATI_SCOPE_PRESENTATION_V13_1
        # CANONICAL ANALYSIS SCOPE
        # -------------------------------------------------

        if context_type == "analysis_scope":
            short = specialist_result.get(
                "kort_resultaat"
            )

            operation = str(
                specialist_result.get(
                    "operation"
                )
                or ""
            )

            subject = str(
                specialist_result.get(
                    "subject"
                )
                or ""
            )

            count_semantics = str(
                specialist_result.get(
                    "count_semantics"
                )
                or ""
            )

            answer_lines: list[str] = []

            if short:
                answer_lines.append(
                    str(short)
                )

            if (
                operation == "list"
                and subject == "bands"
            ):
                bands = specialist_result.get(
                    "bands"
                )

                if (
                    isinstance(bands, list)
                    and bands
                    and not short
                ):
                    answer_lines.append(
                        "Banden: "
                        + ", ".join(
                            str(band)
                            for band in bands
                        )
                    )

            data_quality = specialist_result.get(
                "data_quality"
            )

            if not isinstance(
                data_quality,
                dict,
            ):
                data_quality = {}

            if (
                count_semantics
                == "current_registered_scraper_positions"
            ):
                semantic_note = (
                    data_quality.get(
                        "semantic_note"
                    )
                )

                if semantic_note:
                    answer_lines.extend(
                        [
                            "",
                            str(semantic_note),
                        ]
                    )

            if (
                count_semantics
                == "historical_maintenance_ranking_rows"
            ):
                answer_lines.extend(
                    [
                        "",
                        (
                            "Let op: dit betreft "
                            "historische onderhoudsregels "
                            "binnen de canonical scope. "
                            "Dat is niet automatisch dezelfde "
                            "set als de actuele unified "
                            "schraperposities."
                        ),
                    ]
                )

            if operation == "analyse":
                answer_lines.extend(
                    [
                        "",
                        (
                            "De wear-evidence kan historische "
                            "posities/cycli bevatten en wordt "
                            "daarom als aanvullende historie "
                            "naast de actuele unified snapshot "
                            "gebruikt."
                        ),
                    ]
                )

            if answer_lines:
                return "\n".join(
                    answer_lines
                )

        # -------------------------------------------------
        # PRODUCT
        # Structured family_context is authoritative.
        # RAG wordt hier bewust niet als primaire bron
        # gebruikt.
        # -------------------------------------------------

        if (
            action == "product_assistant"
            or context_type == "product_assistant"
        ):
            family_context = specialist_result.get(
                "family_context"
            )

            if isinstance(family_context, dict):
                family_rows = family_context.get(
                    "results"
                )

                if (
                    isinstance(family_rows, list)
                    and family_rows
                    and isinstance(
                        family_rows[0],
                        dict,
                    )
                ):
                    family = family_rows[0]

                    name = (
                        family.get("family_name")
                        or family.get("family_code")
                    )

                    strengths = family.get(
                        "strengths"
                    )

                    limitations = family.get(
                        "limitations"
                    )

                    selection_advice = family.get(
                        "selection_advice"
                    )

                    answer_lines = []

                    if name:
                        answer_lines.append(
                            str(name)
                        )

                    if strengths:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Sterktes: "
                                    f"{strengths}"
                                ),
                            ]
                        )

                    if limitations:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Beperkingen: "
                                    f"{limitations}"
                                ),
                            ]
                        )

                    if selection_advice:
                        answer_lines.extend(
                            [
                                "",
                                (
                                    "Selectieadvies: "
                                    f"{selection_advice}"
                                ),
                            ]
                        )

                    include_inventory = "inventory" in requested
                    include_price = "price" in requested

                    if include_inventory or include_price:
                        article_lines = _build_product_article_lines(
                            specialist_result,
                            include_inventory=include_inventory,
                            include_price=include_price,
                        )

                        if article_lines:
                            answer_lines.extend(
                                [
                                    "",
                                    *article_lines,
                                ]
                            )

                    if answer_lines:
                        return "\n".join(
                            answer_lines
                        )

        # -------------------------------------------------
        # ORG
        # Alleen nested structured ORG-result gebruiken.
        # -------------------------------------------------

        if (
            action == "org_assistant"
            or context_type == "org_assistant"
        ):
            org_result = specialist_result.get(
                "result"
            )

            if not isinstance(
                org_result,
                dict,
            ):
                continue

            org_status = str(
                org_result.get("status")
                or specialist_result.get("status")
                or ""
            ).lower()

            message = org_result.get(
                "message"
            )

            if (
                org_status == "not_found"
                and message
            ):
                return str(message)

            mode = str(
                specialist_result.get("mode")
                or ""
            )

            if mode == "location_info":
                location_rows = org_result.get(
                    "results"
                )

                if isinstance(
                    location_rows,
                    list,
                ):
                    locations = []

                    for location in location_rows:
                        if not isinstance(
                            location,
                            dict,
                        ):
                            continue

                        address = location.get(
                            "adres"
                        )

                        place = location.get(
                            "plaats"
                        )

                        label = (
                            location.get("locatie")
                            or place
                        )

                        # Alleen concrete locatiegegevens.
                        # De algemene firma-routeringsregel
                        # zonder adres/plaats wordt niet als
                        # vestigingsadres gepresenteerd.
                        if address:
                            if label:
                                locations.append(
                                    f"- {label}: {address}"
                                )
                            else:
                                locations.append(
                                    f"- {address}"
                                )

                        elif place:
                            land = location.get(
                                "land"
                            )

                            value = str(place)

                            if land:
                                value += (
                                    f", {land}"
                                )

                            if label:
                                locations.append(
                                    f"- {label}: {value}"
                                )
                            else:
                                locations.append(
                                    f"- {value}"
                                )

                    if locations:
                        return "\n".join(
                            [
                                "Promati is gevestigd op:",
                                *locations,
                            ]
                        )


            # PROMATI_ORG_FUNCTION_PRESENTATION_V1
            if mode == "function_info":
                function_rows = org_result.get(
                    "results"
                )

                if not isinstance(
                    function_rows,
                    list,
                ):
                    continue

                valid_rows = [
                    row
                    for row in function_rows
                    if isinstance(row, dict)
                ]

                if not valid_rows:
                    continue

                row = valid_rows[0]

                display_name = (
                    row.get("weergavenaam")
                    or "Onbekende persoon"
                )

                function_name = (
                    row.get("officiele_functienaam")
                    or row.get("functie_naam")
                )

                department = row.get(
                    "afdeling"
                )

                core_tasks = row.get(
                    "kerntaken"
                )

                answer_lines = []

                if function_name:
                    answer_lines.append(
                        f"{display_name} is "
                        f"{function_name}."
                    )
                else:
                    answer_lines.append(
                        f"Functiegegevens gevonden "
                        f"voor {display_name}."
                    )

                if department:
                    answer_lines.append(
                        f"Afdeling: {department}."
                    )

                if core_tasks:
                    answer_lines.extend(
                        [
                            "",
                            "Kerntaken:",
                            str(core_tasks),
                        ]
                    )

                return "\n".join(
                    answer_lines
                )

        # -------------------------------------------------
        # TECHNICAL - CEMA
        #
        # Het specialistresultaat bevat de CEMA-bron,
        # maar niet de volledige definitie van CEMA.
        # De formatter vult die dus niet uit zichzelf aan.
        # -------------------------------------------------

        if (
            action == "technical_assistant"
            or context_type == "technical_assistant"
        ):
            source_code = (
                specialist_result.get(
                    "source_code"
                )
            )

            if (
                source_code
                == "CEMA_BELT_CONVEYORS_7"
            ):
                technical_context = (
                    specialist_result.get(
                        "technical_context"
                    )
                )

                source_title = None

                if isinstance(
                    technical_context,
                    dict,
                ):
                    technical_rows = (
                        technical_context.get(
                            "results"
                        )
                    )

                    if isinstance(
                        technical_rows,
                        list,
                    ):
                        for row in technical_rows:
                            if not isinstance(
                                row,
                                dict,
                            ):
                                continue

                            candidate = row.get(
                                "source_title"
                            )

                            if candidate:
                                source_title = str(
                                    candidate
                                )
                                break

                # -----------------------------------------
                # Grounded CEMA definition
                #
                # Alleen used_context geldt als bronbewijs.
                # rag_context.antwoord is op zichzelf
                # nadrukkelijk niet voldoende.
                # -----------------------------------------

                full_name = (
                    "Conveyor Equipment Manufacturers Association"
                )

                grounded_full_name = False

                rag_context = (
                    specialist_result.get(
                        "rag_context"
                    )
                )

                if isinstance(
                    rag_context,
                    dict,
                ):
                    used_context = (
                        rag_context.get(
                            "used_context"
                        )
                    )

                    if isinstance(
                        used_context,
                        list,
                    ):
                        for item in used_context:

                            context_text = None

                            if isinstance(
                                item,
                                str,
                            ):
                                context_text = item

                            elif isinstance(
                                item,
                                dict,
                            ):
                                candidate_text = (
                                    item.get(
                                        "text"
                                    )
                                )

                                if isinstance(
                                    candidate_text,
                                    str,
                                ):
                                    context_text = (
                                        candidate_text
                                    )

                            if not context_text:
                                continue

                            if (
                                full_name.casefold()
                                in context_text.casefold()
                            ):
                                grounded_full_name = True
                                break

                if grounded_full_name:
                    if source_title:
                        return (
                            f"CEMA staat voor {full_name}. "
                            f"Bron: {source_title}."
                        )

                    return (
                        f"CEMA staat voor {full_name}."
                    )

                if source_title:
                    return (
                        "CEMA-referentiegegevens zijn "
                        f"beschikbaar uit {source_title}. "
                        "In dit specialistresultaat is "
                        "geen definitierecord van CEMA "
                        "aanwezig."
                    )

                return (
                    "CEMA-referentiegegevens zijn "
                    "beschikbaar, maar in dit "
                    "specialistresultaat is geen "
                    "definitierecord van CEMA aanwezig."
                )

    return None

def run_orchestrator(
    payload: OrchestratorAskRequest,
    sender: Sender | None = None,
) -> dict[str, Any]:
    """
    Centrale orchestrator-service.

    Flow:
        vraag
        -> understanding
        -> planning
        -> execution
        -> stabiele response

    Deze service bevat bewust:
    - geen FastAPI-router;
    - geen databasecode;
    - geen domein-SQL;
    - geen automatische fallback-relaxation.

    Die verantwoordelijkheden blijven gescheiden.
    """
    # PROMATI_ORCHESTRATOR_OBSERVABILITY_RUN_V1
    timings = (
        _new_observability_timings()
    )
    counts = (
        _new_observability_counts()
    )
    run_started = _observability_now()

    question = (
        payload.q
        if payload.q
        else payload.vraag
    ).strip()

    # PROMATI_CONVERSATION_SCOPE_GROUNDING_V1
    conversation_context = (
        _model_to_dict(
            payload.conversation_context
        )
        if payload.conversation_context
        is not None
        else None
    )

    plan = _observability_call(
        timings,
        "understanding",
        understand_query,
        question,
        conversation_context=conversation_context,
    )

    plan = _observability_call(
        timings,
        "research_requirement",
        assess_research_requirement,
        plan,
    )

    plan = _observability_call(
        timings,
        "planning",
        build_execution_plan,
        plan,
    )

    typed_execution_results = []

    results, trace = _observability_call(
        timings,
        "initial_specialist",
        execute_plan,
        plan,
        sender=sender,
        shadow_observer=(
            typed_execution_results.append
        ),
    )

    attempts = _observability_get(
        trace,
        "attempts",
        [],
    )

    if not isinstance(
        attempts,
        (list, tuple),
    ):
        attempts = []

    counts["execution_attempts"] = len(
        attempts
    )

    # results bevat alleen werkelijk uitgevoerde
    # specialisttransportcalls. Een ontbrekend endpoint
    # komt wel in trace.attempts maar niet in results.
    counts["initial_specialist_calls"] = len(
        results
    )

    counts["initial_raw_result_rows"] = sum(
        _observability_nonnegative_int(
            _observability_get(
                attempt,
                "result_count",
                0,
            )
        )
        for attempt in attempts
    )

    evidence_pipeline = None

    initial_evidence_items = ()
    research_execution = None
    reconciliation = None

    try:
        requirement_set = (
            _observability_call(
                timings,
                "evidence_requirement_lookup",
                get_requirement_set,
                plan.intent,
            )
        )

        specialist_research_blocked = any(
            isinstance(
                item.get("result"),
                dict,
            )
            and str(
                item["result"].get(
                    "status",
                    "",
                )
            ).lower()
            == "clarification_required"
            for item in results
            if isinstance(
                item,
                dict,
            )
        )

        if (
            requirement_set is not None
            and not plan.clarification_required
            and not specialist_research_blocked
        ):
            retrieved_at = datetime.now(
                timezone.utc
            )

            normalization_started = (
                _observability_now()
            )

            try:
                initial_evidence_items = tuple(
                    evidence_item
                    for execution_result
                    in typed_execution_results
                    for evidence_item
                    in normalize_execution_result_evidence(
                        execution_result,
                        retrieved_at=retrieved_at,
                    )
                )
            finally:
                timings[
                    "evidence_normalization"
                ] = (
                    _observability_elapsed_ms(
                        normalization_started
                    )
                )

                counts[
                    "initial_evidence_items"
                ] = len(
                    initial_evidence_items
                )

            initial_assessment = (
                _observability_call(
                    timings,
                    "evidence_assessment",
                    assess_evidence,
                    requirement_set,
                    initial_evidence_items,
                    target_entity_ids=None,
                    now=retrieved_at,
                )
            )

            research_decision = (
                _observability_call(
                    timings,
                    "evidence_research_gate",
                    decide_research_requirement,
                    initial_assessment,
                )
            )

            research_execution = (
                _observability_call(
                    timings,
                    "evidence_research",
                    execute_bounded_research,
                    research_decision,
                    plan,
                    list(results),
                    sender=sender,
                )
            )

            phase_c_agent_metadata = (
                _observability_get(
                    research_execution,
                    "agent_metadata",
                    None,
                )
            )

            if isinstance(
                phase_c_agent_metadata,
                dict,
            ):
                counts[
                    "phase_c_research_follow_up_specialist_calls"
                ] = (
                    _observability_nonnegative_int(
                        phase_c_agent_metadata.get(
                            "follow_up_specialist_calls"
                        )
                    )
                )

                counts[
                    "phase_c_ai_calls"
                ] = (
                    _observability_nonnegative_int(
                        phase_c_agent_metadata.get(
                            "total_ai_calls_used"
                        )
                    )
                )

            reconciliation = (
                _observability_call(
                    timings,
                    "reconciliation",
                    reconcile_evidence,
                    requirement_set,
                    initial_evidence_items,
                    initial_assessment,
                    research_execution,
                    retrieved_at=retrieved_at,
                    target_entity_ids=None,
                    now=retrieved_at,
                )
            )

            reconciled_items = (
                _observability_get(
                    reconciliation,
                    "reconciled_evidence_items",
                    (),
                )
            )

            if isinstance(
                reconciled_items,
                (list, tuple),
            ):
                counts[
                    "reconciled_evidence_items"
                ] = len(
                    reconciled_items
                )

            synthesis = (
                _observability_call(
                    timings,
                    "synthesis",
                    synthesize_grounded_evidence,
                    reconciliation,
                )
            )

            evidence_pipeline = (
                _evidence_pipeline_to_dict(
                    {
                        "requirement_set_id": (
                            requirement_set
                            .requirement_set_id
                        ),
                        "initial_assessment": (
                            initial_assessment
                        ),
                        "research_decision": (
                            research_decision
                        ),
                        "research_execution": (
                            research_execution
                        ),
                        "reconciliation": (
                            reconciliation
                        ),
                        "synthesis": synthesis,
                    }
                )
            )

    except Exception:
        # C8 is additive and fail-open: the legacy
        # response path remains authoritative.
        evidence_pipeline = None

    specialist_clarification = None

    for item in results:
        specialist_result = item.get(
            "result"
        )

        if not isinstance(
            specialist_result,
            dict,
        ):
            continue

        specialist_status = str(
            specialist_result.get(
                "status",
                "",
            )
        ).lower()

        if (
            specialist_status
            == "clarification_required"
        ):
            specialist_clarification = (
                specialist_result
            )
            break

    clarification = {
        "required": (
            plan.clarification_required
        ),
        "question": (
            plan.clarification_question
        ),
    }

    if plan.clarification_required:
        # Query-understanding clarification houdt
        # de hoogste prioriteit.
        status = "clarification_required"

    elif (
        specialist_clarification
        is not None
    ):
        # Een specialist kan tijdens uitvoering ontdekken
        # dat aanvullende context nodig is, bijvoorbeeld
        # bij een band/installatie-conflict.
        clarification_question = (
            specialist_clarification.get(
                "message"
            )
        )

        if not clarification_question:
            detail = (
                specialist_clarification.get(
                    "clarification"
                )
            )

            if isinstance(
                detail,
                dict,
            ):
                clarification_question = (
                    detail.get(
                        "question"
                    )
                )

            elif isinstance(
                detail,
                str,
            ):
                clarification_question = (
                    detail
                )

        if not clarification_question:
            clarification_question = (
                "Kun je de ontbrekende context "
                "verduidelijken?"
            )

        clarification = {
            "required": True,
            "question": str(
                clarification_question
            ),
        }

        status = (
            "clarification_required"
        )

    elif (
        plan.execution_steps
        and not has_service_accepted_execution(
            typed_execution_results,
            results,
        )
    ):
        status = "error"

    else:
        status = "ok"

    # PROMATI_BOUNDED_RESEARCH_V1_GATE
    # Deterministic specialist execution always happens
    # first. Only a clear, successful research_required
    # plan may use one bounded AI synthesis call.
    research = {
        "status": "not_required",
        "required": bool(
            plan.research_required
        ),
        "mode": "bounded_synthesis_v1",
        "ai_calls_used": 0,
        "max_ai_calls": 1,
        "follow_up_rounds_used": 0,
        "max_follow_up_rounds": 0,
        "answer": None,
    }

    if (
        status == "ok"
        and plan.research_required
        and not clarification.get(
            "required"
        )
    ):
        research_agent_enabled = (
            _research_agent_enabled()
        )

        if research_agent_enabled:
            research = (
                _observability_call(
                    timings,
                    "plan_research",
                    run_bounded_research_agent,
                    plan,
                    results,
                    sender=sender,
                )
            )
        else:
            research = (
                _observability_call(
                    timings,
                    "plan_research",
                    run_bounded_research,
                    plan,
                    results,
                )
            )

    plan_research_agent = None

    if isinstance(
        research,
        dict,
    ):
        raw_agent = research.get(
            "agent"
        )

        if isinstance(
            raw_agent,
            dict,
        ):
            plan_research_agent = (
                raw_agent
            )

    if (
        plan_research_agent
        is not None
    ):
        counts[
            "plan_research_follow_up_specialist_calls"
        ] = (
            _observability_nonnegative_int(
                plan_research_agent.get(
                    "follow_up_specialist_calls"
                )
            )
        )

        if (
            "total_ai_calls_used"
            in plan_research_agent
        ):
            counts[
                "plan_research_ai_calls"
            ] = (
                _observability_nonnegative_int(
                    plan_research_agent.get(
                        "total_ai_calls_used"
                    )
                )
            )
        else:
            counts[
                "plan_research_ai_calls"
            ] = (
                _observability_nonnegative_int(
                    research.get(
                        "ai_calls_used"
                    )
                )
            )

    elif isinstance(
        research,
        dict,
    ):
        counts[
            "plan_research_ai_calls"
        ] = (
            _observability_nonnegative_int(
                research.get(
                    "ai_calls_used"
                )
            )
        )

    counts[
        "research_follow_up_specialist_calls"
    ] = (
        counts[
            "phase_c_research_follow_up_specialist_calls"
        ]
        + counts[
            "plan_research_follow_up_specialist_calls"
        ]
    )

    counts["total_specialist_calls"] = (
        counts[
            "initial_specialist_calls"
        ]
        + counts[
            "research_follow_up_specialist_calls"
        ]
    )

    counts["total_ai_calls"] = (
        counts[
            "phase_c_ai_calls"
        ]
        + counts[
            "plan_research_ai_calls"
        ]
    )

    presentation_started = (
        _observability_now()
    )

    try:
        answer = _build_user_answer(
            results,
            requested_information=(
                plan.requested_information
            ),
        )

        if (
            research.get(
                "status"
            )
            == "ok"
            and research.get(
                "answer"
            )
        ):
            answer = str(
                research["answer"]
            )

        if answer:
            answer = (
                repair_mojibake_text(
                    answer
                )
            )
    finally:
        timings["presentation"] = (
            _observability_elapsed_ms(
                presentation_started
            )
        )

    response_build_started = (
        _observability_now()
    )

    try:
        # PROMATI_PUBLIC_RESPONSE_PROFILE_V1
        #
        # De volledige evidence pipeline blijft intern
        # bestaan. Alleen de publieke serialisatie wordt
        # geprojecteerd.
        # Debug/include_trace behoudt het volledige
        # Phase-C object voor regressie en audit.
        public_evidence_pipeline = (
            evidence_pipeline
            if payload.include_trace
            else (
                _compact_evidence_pipeline_for_public_response(
                    evidence_pipeline
                )
            )
        )

        public_results = (
            results
            if payload.include_trace
            else compact_results_for_public_response(
                results,
                requested_information=(
                    plan.requested_information
                ),
            )
        )

        response = {
            "status": status,
            "answer": answer,
            "context_type": "orchestrator",
            "question": question,
            "query_plan": (
                _model_to_dict(
                    plan
                )
            ),
            "research": research,
            "clarification": (
                clarification
            ),
            "results": public_results,
            "evidence_pipeline": (
                public_evidence_pipeline
            ),
        }

        if payload.include_trace:
            response["trace"] = (
                _model_to_dict(
                    trace
                )
            )
        else:
            response["trace"] = None

    finally:
        timings["response_build"] = (
            _observability_elapsed_ms(
                response_build_started
            )
        )

    # total is de wall-clock tijd van de service tot en
    # met de opbouw van de Python-response. HTTP JSON-
    # serialisatie valt bewust buiten dit contract.
    timings["total"] = (
        _observability_elapsed_ms(
            run_started
        )
    )

    response["observability"] = {
        "contract_version": (
            ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION
        ),
        "timings_ms": dict(
            timings
        ),
        "counts": dict(
            counts
        ),
    }

    return response
