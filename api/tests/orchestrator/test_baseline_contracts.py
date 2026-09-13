from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.orchestrator import service
from app.orchestrator.evidence_requirement_catalog import get_requirement_set
from app.orchestrator.executor import ACTION_ENDPOINTS
from app.orchestrator.planner import build_execution_plan
from app.orchestrator.query_classification import classify_query
from app.orchestrator.response_shaping import compact_orchestrator_response, shape_orchestrator_response
from app.orchestrator.routing_sanity import apply_routing_sanity
from app.orchestrator.specialist_registry import SPECIALIST_CONTRACTS
from app.orchestrator.understanding import understand_query
from app.routers import orchestrator_api


API_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = API_ROOT / "app"
FORBIDDEN_PUBLIC_MARKERS = (
    "evidence_ids_used", "included_evidence_ids", "excluded_evidence_ids",
    "task_coverage_gate_cp10", "task_presenter_cp11", "/analysis/",
    "/product/", "latest_position_measurement:", "latest_blade_height:",
    "traceback (most recent call last)", "select * from",
)
LEGACY_PARSE_EXCEPTIONS = {Path("app/routers/analysis_api_v6.py")}


def _plan(question: str):
    return build_execution_plan(apply_routing_sanity(understand_query(question)))


def test_all_active_python_files_parse():
    failures = []
    for path in APP_ROOT.rglob("*.py"):
        if ".bak" in path.name:
            continue
        if path.relative_to(API_ROOT) in LEGACY_PARSE_EXCEPTIONS:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except Exception as exc:  # pragma: no cover - assertion diagnostic
            failures.append(f"{path.relative_to(API_ROOT)}: {exc}")
    assert failures == []


def test_known_inactive_legacy_parse_gap_is_explicit():
    path = API_ROOT / "app" / "routers" / "analysis_api_v6.py"
    try:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as exc:
        assert "unterminated triple-quoted string" in str(exc)
    else:  # pragma: no cover - closes the gap intentionally
        raise AssertionError("Remove analysis_api_v6.py from LEGACY_PARSE_EXCEPTIONS")


def test_public_router_imports_final_run_orchestrator_definition():
    assert orchestrator_api.run_orchestrator is service.run_orchestrator
    assert inspect.getsourcelines(service.run_orchestrator)[1] == 9567


def test_every_planner_action_has_executor_and_specialist_contract():
    questions = (
        "Wat is de laatste inspectiestatus van band A319?",
        "Geef productinformatie over BB-U.",
        "Leg CEMA uit.",
        "Controleer RFQ-readiness voor RFQ 123.",
        "Wie is verantwoordelijk voor VCA binnen Promati?",
        "Welke dependencies heeft view vw_meshoogte_latest_per_scraper_clean?",
    )
    actions = {step.action for question in questions for step in _plan(question).execution_steps}
    assert actions <= set(ACTION_ENDPOINTS)
    assert actions <= set(SPECIALIST_CONTRACTS)


def test_every_observed_requested_intent_has_requirement_or_documented_exception():
    exceptions = {
        "unknown", "conversation", "system_meta", "clarification_only",
        # Diagnostics-meta currently has no evidence requirement set; CP0 gap.
        "diagnostics_view_dependencies",
    }
    questions = (
        "Wat is de laatste inspectiestatus van band A319?",
        "Wat heeft prioriteit qua onderhoud op B12?",
        "Geef productinformatie over BB-U.",
        "Wat is de actuele prijs en voorraad van BB-U?",
        "Leg CEMA uit.",
        "Controleer RFQ-readiness voor RFQ 123.",
        "Wie is verantwoordelijk voor VCA binnen Promati?",
        "Welke dependencies heeft view vw_meshoogte_latest_per_scraper_clean?",
    )
    missing = []
    for question in questions:
        plan = _plan(question)
        for task in plan.intent_tasks:
            if task.polarity == "requested" and task.intent not in exceptions:
                if get_requirement_set(task.intent) is None:
                    missing.append(f"{task.domain.value}:{task.intent}")
    assert sorted(set(missing)) == []


def test_compact_is_bounded_has_trace_and_never_leaks_debug_fields():
    answer = "Veilige samenvatting."
    raw = {
        "status": "ok", "answer": answer, "trace_id": "trace-synthetic",
        "query_plan": {"domains": ["inspection"], "intent_tasks": []},
        "results": [{"accepted": True}],
        "evidence_pipeline": {
            "task_coverage_gate_cp10": {"authoritative": True},
            "task_presenter_cp11": {"evidence_ids_used": ["secret"]},
        },
    }
    compact = compact_orchestrator_response(raw)
    serialized = repr(compact).casefold()
    assert compact["trace_id"] == "trace-synthetic"
    assert compact["answer"] == answer
    assert "evidence_pipeline" not in compact
    assert all(marker.casefold() not in serialized for marker in FORBIDDEN_PUBLIC_MARKERS)


def test_debug_preserves_authority_pipeline_and_public_answer_stays_clean():
    raw = {
        "status": "ok", "answer": "Veilige publieke tekst.", "trace_id": "trace-synthetic",
        "query_plan": {"domains": ["technical"], "intent_tasks": []},
        "evidence_pipeline": {
            "task_authority_gate_cp9": {"authoritative": True},
            "task_coverage_gate_cp10": {"authoritative": True},
            "task_presenter_cp11": {"authoritative": True},
            "task_concise_composer_cp12": {"authoritative": True},
            "task_research_semantics_cp13": {"public_answer_authority": False},
            "release_gate_cp15": {"release_ready": True},
        },
    }
    debug = shape_orchestrator_response(raw, "debug")
    assert debug is raw
    for marker in ("cp9", "cp10", "cp11", "cp12", "cp13", "cp15"):
        assert marker in repr(debug["evidence_pipeline"]).casefold()
    assert all(marker.casefold() not in debug["answer"].casefold() for marker in FORBIDDEN_PUBLIC_MARKERS)
