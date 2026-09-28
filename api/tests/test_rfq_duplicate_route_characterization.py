from __future__ import annotations

import ast
import copy
import sys
import unittest
import warnings
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Match


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


RFQ_SOURCE = ROOT / "app" / "routers" / "rfq_api.py"

@dataclass(frozen=True)
class HandlerIdentity:
    parameters: tuple[str, ...]
    required_calls: frozenset[str]
    required_strings: frozenset[str]

    def label(self) -> str:
        discriminating_calls = {
            "fetch_one",
            "get_rfq_position_datasheet_html",
            "json_dumps",
            "render_landscape_rfq_html",
            "update_rfq_workflow_status",
        }
        discriminating_strings = {
            "Positie niet gevonden",
            "Position not found",
            "Testfase positie verwijderd",
            "rfq-",
            "rfq_position_deleted",
            "trommel-datasheet-",
        }
        return "|".join(
            (
                ",".join(self.parameters),
                ",".join(sorted(self.required_calls & discriminating_calls)),
                ",".join(sorted(self.required_strings & discriminating_strings)),
            )
        )


@dataclass(frozen=True)
class SourceRegistration:
    line: int
    name: str
    identity: HandlerIdentity


KNOWN_SOURCE_HANDLER_IDENTITIES = {
    "delete_rfq_position": (
        HandlerIdentity(
            ("rfq_id", "position_id", "deleted_by"),
            frozenset({"fetch_one", "execute_one", "update_rfq_workflow_status"}),
            frozenset({"Testfase positie verwijderd"}),
        ),
        HandlerIdentity(
            ("rfq_id", "position_id"),
            frozenset({"execute_one", "HTTPException"}),
            frozenset({"Position not found"}),
        ),
        HandlerIdentity(
            ("rfq_id", "position_id"),
            frozenset({"execute_one", "HTTPException", "json_dumps"}),
            frozenset({"Positie niet gevonden", "rfq_position_deleted"}),
        ),
    ),
    "get_rfq_position_datasheet_pdf": (
        HandlerIdentity(
            ("rfq_id", "position_id", "commercial_approved", "view_mode"),
            frozenset({"render_landscape_rfq_html", "HTML.write_pdf", "Response"}),
            frozenset({"rfq-"}),
        ),
        HandlerIdentity(
            ("rfq_id", "position_id", "commercial_approved", "view_mode"),
            frozenset({"get_rfq_position_datasheet_html", "HTML.write_pdf", "Response"}),
            frozenset({"trommel-datasheet-", "utf-8"}),
        ),
    ),
}

KNOWN_REGISTERED_ROUTE_IDENTITIES = {
    ("DELETE", "/{rfq_id}/positions/{position_id}"): (
        KNOWN_SOURCE_HANDLER_IDENTITIES["delete_rfq_position"][0],
    ),
    ("GET", "/{rfq_id}/positions/{position_id}/datasheet/pdf"): KNOWN_SOURCE_HANDLER_IDENTITIES[
        "get_rfq_position_datasheet_pdf"
    ],
}


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_path(node.value)
        return f"{parent}.{node.attr}" if parent else None
    if isinstance(node, ast.Call):
        return _attribute_path(node.func)
    return None


def _handler_identity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> HandlerIdentity:
    calls = {
        call_name
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        if (call_name := _attribute_path(child.func)) is not None
    }
    strings = {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }
    parameters = tuple(argument.arg for argument in node.args.args)
    return HandlerIdentity(parameters, frozenset(calls), frozenset(strings))


def _source_registrations(
    tree: ast.Module | None = None,
) -> dict[tuple[str, str], list[SourceRegistration]]:
    tree = tree or ast.parse(RFQ_SOURCE.read_text(encoding="utf-8"))
    registrations: dict[tuple[str, str], list[SourceRegistration]] = {}

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not (
                isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                and decorator.func.attr in {"delete", "get"}
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                continue

            key = (decorator.func.attr.upper(), decorator.args[0].value)
            if key in KNOWN_REGISTERED_ROUTE_IDENTITIES and any(
                keyword.arg == "operation_id" for keyword in decorator.keywords
            ):
                raise AssertionError(f"explicit operation_id introduced for {key}")
            registrations.setdefault(key, []).append(
                SourceRegistration(node.lineno, node.name, _handler_identity(node))
            )

    return registrations


def _source_handler_definitions(
    tree: ast.Module | None = None,
) -> dict[str, list[SourceRegistration]]:
    tree = tree or ast.parse(RFQ_SOURCE.read_text(encoding="utf-8"))
    definitions: dict[str, list[SourceRegistration]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in KNOWN_SOURCE_HANDLER_IDENTITIES:
            definitions.setdefault(node.name, []).append(
                SourceRegistration(node.lineno, node.name, _handler_identity(node))
            )
    return definitions


def _assert_source_handler_definitions(
    definitions: dict[str, list[SourceRegistration]],
) -> None:
    for name, expected_identities in KNOWN_SOURCE_HANDLER_IDENTITIES.items():
        observed = definitions.get(name, [])
        if len(observed) != len(expected_identities) or any(
            not _identity_matches(registration.identity, expected)
            for registration, expected in zip(observed, expected_identities, strict=True)
        ):
            raise AssertionError(f"source handler identities changed for {name}")
        if [registration.line for registration in observed] != sorted(
            registration.line for registration in observed
        ):
            raise AssertionError(f"source handler order changed for {name}")


def _assert_registered_route_identities(
    registrations: dict[tuple[str, str], list[SourceRegistration]],
) -> None:
    for key, expected_identities in KNOWN_REGISTERED_ROUTE_IDENTITIES.items():
        observed = registrations.get(key, [])
        if len(observed) != len(expected_identities) or any(
            not _identity_matches(registration.identity, expected)
            for registration, expected in zip(observed, expected_identities, strict=True)
        ):
            raise AssertionError(f"registered handler identities changed for {key}")
        expected_name = (
            "delete_rfq_position"
            if key[0] == "DELETE"
            else "get_rfq_position_datasheet_pdf"
        )
        if tuple(registration.name for registration in observed) != (expected_name,) * len(observed):
            raise AssertionError(f"registered handler names changed for {key}")
        if [registration.line for registration in observed] != sorted(
            registration.line for registration in observed
        ):
            raise AssertionError(f"duplicate source order changed for {key}")


def _identity_matches(
    observed: HandlerIdentity,
    expected: HandlerIdentity,
) -> bool:
    return (
        observed.parameters == expected.parameters
        and expected.required_calls <= observed.required_calls
        and expected.required_strings <= observed.required_strings
    )


def _registered_routes_for_key(
    key: tuple[str, str],
) -> list[SourceRegistration]:
    registrations = _source_registrations()
    _assert_registered_route_identities(registrations)
    return registrations[key]


def _delete_decorator(node: ast.FunctionDef) -> ast.Call:
    decorators = [
        decorator
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and isinstance(decorator.func.value, ast.Name)
        and decorator.func.value.id == "router"
        and decorator.func.attr == "delete"
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
        and decorator.args[0].value == "/{rfq_id}/positions/{position_id}"
    ]
    if len(decorators) != 1:
        raise AssertionError("expected exactly one RFQ position DELETE decorator")
    return decorators[0]


def _remove_duplicate_delete_decorators(tree: ast.Module) -> ast.Module:
    delete_nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "delete_rfq_position"
    ]
    if len(delete_nodes) != 3:
        raise AssertionError("expected all three RFQ DELETE function definitions")
    for node in delete_nodes[1:]:
        node.decorator_list = [
            decorator for decorator in node.decorator_list
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                and decorator.func.attr == "delete"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and decorator.args[0].value == "/{rfq_id}/positions/{position_id}"
            )
        ]
    return tree


def _named_stub(name: str, marker: str):
    def endpoint():
        return {"marker": marker}

    endpoint.__name__ = name
    return endpoint


class RfqDuplicateRouteCharacterizationTests(unittest.TestCase):
    def test_source_preserves_all_handler_definitions_and_registers_only_the_first_delete(self):
        registrations = _source_registrations()
        definitions = _source_handler_definitions()
        _assert_source_handler_definitions(definitions)
        _assert_registered_route_identities(registrations)

        delete_definitions = definitions["delete_rfq_position"]
        self.assertEqual(len(delete_definitions), 3)
        self.assertEqual(
            len({registration.identity.label() for registration in delete_definitions}),
            3,
        )
        delete_routes = registrations[("DELETE", "/{rfq_id}/positions/{position_id}")]
        self.assertEqual(delete_routes, [delete_definitions[0]])
        self.assertEqual(
            len(registrations[("GET", "/{rfq_id}/positions/{position_id}/datasheet/pdf")]),
            2,
        )

    def test_candidate_ast_is_exactly_the_in_memory_removal_of_the_two_duplicate_decorators(self):
        candidate = ast.parse(RFQ_SOURCE.read_text(encoding="utf-8"))
        reconstructed_start = copy.deepcopy(candidate)
        delete_nodes = [
            node for node in reconstructed_start.body
            if isinstance(node, ast.FunctionDef) and node.name == "delete_rfq_position"
        ]
        self.assertEqual(len(delete_nodes), 3)
        first_decorator = _delete_decorator(delete_nodes[0])
        for node in delete_nodes[1:]:
            node.decorator_list.append(copy.deepcopy(first_decorator))

        expected = _remove_duplicate_delete_decorators(reconstructed_start)
        self.assertEqual(
            ast.dump(expected, include_attributes=False),
            ast.dump(candidate, include_attributes=False),
        )

    def test_handler_implementation_swap_is_detected_without_editing_source(self):
        tree = ast.parse(RFQ_SOURCE.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(tree)
        delete_nodes = [
            node
            for node in mutated.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "delete_rfq_position"
        ]
        self.assertEqual(len(delete_nodes), 3)
        delete_nodes[0].args, delete_nodes[1].args = (
            delete_nodes[1].args,
            delete_nodes[0].args,
        )
        delete_nodes[0].body, delete_nodes[1].body = (
            delete_nodes[1].body,
            delete_nodes[0].body,
        )

        with self.assertRaises(AssertionError):
            _assert_source_handler_definitions(_source_handler_definitions(mutated))

    def test_reintroduced_second_delete_decorator_is_rejected_in_memory(self):
        mutated = ast.parse(RFQ_SOURCE.read_text(encoding="utf-8"))
        delete_nodes = [
            node for node in mutated.body
            if isinstance(node, ast.FunctionDef) and node.name == "delete_rfq_position"
        ]
        delete_nodes[1].decorator_list.append(copy.deepcopy(_delete_decorator(delete_nodes[0])))
        with self.assertRaises(AssertionError):
            _assert_registered_route_identities(_source_registrations(mutated))

    def test_isolated_fastapi_registration_dispatches_the_registered_identity(self):
        """Route matching is isolated; this suite intentionally does not open ASGI sockets."""
        for method, path in KNOWN_REGISTERED_ROUTE_IDENTITIES:
            with self.subTest(method=method, path=path):
                app = FastAPI()
                registrations = _registered_routes_for_key((method, path))
                stubs = [
                    _named_stub(registration.name, registration.identity.label())
                    for registration in registrations
                ]
                for registration, stub in zip(registrations, stubs, strict=True):
                    app.add_api_route(
                        path,
                        stub,
                        methods=[method],
                        name=registration.name,
                        openapi_extra={
                            "x-characterization-source-identity": registration.identity.label()
                        },
                    )

                routes = [
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == path
                    and method in (getattr(route, "methods", None) or set())
                ]
                self.assertEqual([route.endpoint for route in routes], stubs)
                self.assertEqual(len({route.unique_id for route in routes}), 1)

                scope = {
                    "type": "http",
                    "method": method,
                    "path": path.replace("{rfq_id}", "rfq-1").replace(
                        "{position_id}", "position-1"
                    ),
                    "root_path": "",
                    "scheme": "http",
                    "headers": [],
                }
                matched = [
                    route
                    for route in routes
                    if route.matches(scope)[0] == Match.FULL
                ]
                self.assertIs(matched[0].endpoint, stubs[0])
                self.assertEqual(
                    matched[0].endpoint()["marker"],
                    registrations[0].identity.label(),
                )

                if len(routes) == 1:
                    with warnings.catch_warnings(record=True) as captured:
                        warnings.simplefilter("always")
                        schema = app.openapi()
                    self.assertFalse(captured)
                else:
                    with self.assertWarnsRegex(UserWarning, "Duplicate Operation ID"):
                        schema = app.openapi()
                operation = schema["paths"][path][method.lower()]
                self.assertEqual(operation["operationId"], routes[-1].unique_id)
                self.assertEqual(
                    operation["x-characterization-source-identity"],
                    registrations[-1].identity.label(),
                )
                self.assertEqual(len(schema["paths"][path]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
