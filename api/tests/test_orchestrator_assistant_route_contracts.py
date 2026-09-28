from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from app.orchestrator import executor  # noqa: E402
from app.orchestrator.executor import execute_plan  # noqa: E402
from app.orchestrator.models import Domain, QueryPlan  # noqa: E402
from app.orchestrator.planner import build_execution_plan  # noqa: E402
from app.orchestrator.specialist_registry import (  # noqa: E402
    SPECIALIST_CONTRACTS,
)


QUESTION = "synthetische contractvraag zonder externe uitvoering"

ASSISTANT_CONTRACTS = {
    Domain.PRODUCT: (
        "product_assistant",
        "/product/assistant/ask",
        {"vraag": QUESTION, "mode": "auto"},
    ),
    Domain.INSPECTION: (
        "analysis_assistant",
        "/analysis/assistant/ask",
        {"vraag": QUESTION, "mode": "auto"},
    ),
    Domain.TECHNICAL: (
        "technical_assistant",
        "/technical/assistant/ask",
        {"vraag": QUESTION, "use_rag": True},
    ),
    Domain.RFQ: (
        "rfq_assistant",
        "/rfq/assistant/ask",
        {"vraag": QUESTION, "mode": "auto"},
    ),
    Domain.ORG: (
        "org_assistant",
        "/org/assistant/ask",
        {"vraag": QUESTION, "firma": "Promati", "mode": "auto"},
    ),
    Domain.DIAGNOSTICS: (
        "diagnostics_assistant",
        "/diagnostics/assistant/ask",
        {
            "vraag": QUESTION,
            "domain": "database",
            "mode": "overview",
            "depth": "normal",
            "limit": 50,
        },
    ),
}

ROUTER_MODULE_SOURCES = {
    "hybrid_api.router": ROOT / "app" / "routers" / "hybrid_api.py",
    "analysis_api_v10.router": ROOT / "app" / "routers" / "analysis_api_v10.py",
}


def _source_tree(source_path: Path, source_text: str | None = None) -> ast.Module:
    return ast.parse(source_text or source_path.read_text(encoding="utf-8"))


def _router_prefix(source_path: Path, source_text: str | None = None) -> str:
    tree = _source_tree(source_path, source_text)

    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "router"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "APIRouter"
        ):
            continue

        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                if not (
                    isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    raise AssertionError("router prefix must be a string literal")
                return keyword.value.value
        return ""

    raise AssertionError(f"APIRouter assignment not found in {source_path}")


def _decorated_routes(
    source_path: Path,
    prefix: str,
    source_text: str | None = None,
) -> list[tuple[str, str, str]]:
    tree = _source_tree(source_path, source_text)
    routes: list[tuple[str, str, str]] = []

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
                and decorator.func.attr == "post"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                continue
            routes.append(("POST", prefix + decorator.args[0].value, node.name))

    return routes


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_path(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _main_router_includes() -> dict[str, str]:
    main_source = ROOT / "app" / "main.py"
    tree = ast.parse(main_source.read_text(encoding="utf-8"))
    includes: dict[str, str] = {}

    # This is deliberately a top-level source check.  It catches changes to
    # the active include_router calls, but does not claim that importing main
    # (with its optional imports and runtime dependencies) was exercised.
    for node in tree.body:
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "app"
            and node.value.func.attr == "include_router"
            and node.value.args
        ):
            continue
        router_path = _attribute_path(node.value.args[0])
        if router_path not in ROUTER_MODULE_SOURCES:
            continue

        include_prefix = ""
        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                if not (
                    isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    raise AssertionError("include_router prefix must be a string literal")
                include_prefix = keyword.value.value
        includes[router_path] = include_prefix

    return includes


def _declared_assistant_routes(
    source_overrides: dict[Path, str] | None = None,
) -> list[tuple[str, str, str]]:
    source_overrides = source_overrides or {}
    includes = _main_router_includes()
    routes: list[tuple[str, str, str]] = []

    for router_path, source_path in ROUTER_MODULE_SOURCES.items():
        if router_path not in includes:
            continue
        source_text = source_overrides.get(source_path)
        prefix = includes[router_path] + _router_prefix(source_path, source_text)
        routes.extend(_decorated_routes(source_path, prefix, source_text))

    return routes


def _assert_exact_assistant_routes(
    declared_routes: list[tuple[str, str, str]],
) -> None:
    expected = {
        ("POST", endpoint, f"{action}_ask")
        for action, endpoint, _ in ASSISTANT_CONTRACTS.values()
    }
    for route in expected:
        if declared_routes.count(route) != 1:
            raise AssertionError(f"expected exactly one declared route: {route}")


class OrchestratorAssistantRouteContractTests(unittest.TestCase):
    def test_planner_executor_and_registry_keep_six_assistant_contracts_aligned(self):
        for domain, (action, endpoint, required_payload) in ASSISTANT_CONTRACTS.items():
            with self.subTest(domain=domain.value):
                plan = QueryPlan(
                    original_question=QUESTION,
                    normalized_question=QUESTION,
                    primary_domain=domain,
                    domains=[domain],
                )
                build_execution_plan(plan)

                self.assertEqual(len(plan.execution_steps), 1)
                step = plan.execution_steps[0]
                self.assertEqual(step.action, action)
                self.assertEqual(
                    SPECIALIST_CONTRACTS[action].endpoint,
                    endpoint,
                )
                self.assertTrue(
                    required_payload.items() <= step.params.items(),
                )

                sent: list[tuple[str, dict[str, object]]] = []

                def sender(path: str, payload: dict[str, object]) -> dict[str, object]:
                    sent.append((path, payload))
                    return {"status": "ok", "synthetic": True}

                results, trace = execute_plan(plan, sender)

                self.assertEqual(sent, [(endpoint, step.params)])
                self.assertEqual(results[0]["endpoint"], endpoint)
                self.assertEqual(results[0]["action"], action)
                self.assertTrue(results[0]["accepted"])
                self.assertEqual(trace.attempts[0].action, action)
                self.assertEqual(trace.attempts[0].status, "ok")

    def test_default_sender_posts_planned_payloads_through_requests_transport(self):
        """Exercise the production sender; requests.post is the only mocked boundary."""
        for domain, (action, endpoint, required_payload) in ASSISTANT_CONTRACTS.items():
            with self.subTest(domain=domain.value):
                plan = QueryPlan(
                    original_question=QUESTION,
                    normalized_question=QUESTION,
                    primary_domain=domain,
                    domains=[domain],
                )
                build_execution_plan(plan)
                response = Mock()
                response.json.return_value = {"status": "ok", "synthetic": action}

                with (
                    patch.object(
                        executor, "_api_base_url", return_value="https://transport.invalid/api"
                    ),
                    patch.object(executor.requests, "post", return_value=response) as post,
                ):
                    results, trace = execute_plan(plan)

                self.assertTrue(required_payload.items() <= plan.execution_steps[0].params.items())
                post.assert_called_once_with(
                    f"https://transport.invalid/api{endpoint}",
                    json=plan.execution_steps[0].params,
                    timeout=30,
                )
                response.raise_for_status.assert_called_once_with()
                self.assertEqual(results[0]["endpoint"], endpoint)
                self.assertEqual(results[0]["action"], action)
                self.assertTrue(results[0]["accepted"])
                self.assertEqual(trace.attempts[0].status, "ok")

    def test_default_sender_returns_existing_transport_error_shape(self):
        for domain, (_, endpoint, _) in ASSISTANT_CONTRACTS.items():
            with self.subTest(domain=domain.value):
                with patch.object(
                    executor.requests,
                    "post",
                    side_effect=executor.requests.Timeout("synthetic transport timeout"),
                ):
                    result = executor.default_sender(endpoint, {"vraag": QUESTION})

                self.assertEqual(result["status"], "error")
                self.assertEqual(result["context_type"], "orchestrator_transport")
                self.assertEqual(result["path"], endpoint)
                self.assertFalse(result["write_actions_available"])

    def test_executor_preserves_synthetic_error_results_for_each_assistant_route(self):
        for domain, (action, endpoint, _) in ASSISTANT_CONTRACTS.items():
            with self.subTest(domain=domain.value):
                plan = QueryPlan(
                    original_question=QUESTION,
                    normalized_question=QUESTION,
                    primary_domain=domain,
                    domains=[domain],
                )
                build_execution_plan(plan)

                error_result = {
                    "status": "error",
                    "error": f"synthetic {action} failure",
                }
                results, trace = execute_plan(
                    plan,
                    lambda path, payload: (
                        error_result
                        if path == endpoint and payload == plan.execution_steps[0].params
                        else {"status": "error", "error": "unexpected sender input"}
                    ),
                )

                self.assertFalse(results[0]["accepted"])
                self.assertIs(results[0]["result"], error_result)
                self.assertEqual(trace.attempts[0].action, action)
                self.assertEqual(trace.attempts[0].status, "error")
                self.assertEqual(trace.attempts[0].error, error_result["error"])

    def test_each_registry_endpoint_has_one_matching_post_router_declaration(self):
        includes = _main_router_includes()
        self.assertEqual(
            {"analysis_api_v10.router", "hybrid_api.router"},
            set(includes),
        )
        self.assertEqual(includes, {"analysis_api_v10.router": "", "hybrid_api.router": ""})
        _assert_exact_assistant_routes(_declared_assistant_routes())

    def test_router_prefix_mutation_is_detected_without_editing_production_source(self):
        analysis_source = ROUTER_MODULE_SOURCES["analysis_api_v10.router"]
        original = analysis_source.read_text(encoding="utf-8")
        mutated = original.replace('prefix="/analysis"', 'prefix="/analysis-v2"', 1)
        self.assertNotEqual(original, mutated)

        with self.assertRaises(AssertionError):
            _assert_exact_assistant_routes(
                _declared_assistant_routes({analysis_source: mutated})
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
