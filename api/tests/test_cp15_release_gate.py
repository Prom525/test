from app.orchestrator.release_gate_cp15 import build_release_gate_cp15
from app.orchestrator.response_shaping import compact_orchestrator_response


def _shadow(missing=()):
    missing = list(missing)
    total = 2
    return {"summary": {
        "required_total": total,
        "required_planned": total,
        "required_executed": total - len(missing),
        "required_missing": len(missing),
        "missing_required_tasks": missing,
    }}


def _green_pipeline():
    return {
        "task_authority_gate_cp9": {"contract_version": "promati.orchestrator.task_authority_gate.cp9.v1", "evaluated": True, "blocked": False, "reason": "required_task_execution_covered"},
        "task_coverage_gate_cp10": {"contract_version": "promati.orchestrator.task_coverage_gate.cp10.v1", "evaluated": True, "blocked": False, "authoritative": True, "coverage_complete": True, "reason": "required_execution_and_coverage_authoritative"},
        "task_presenter_cp11": {"contract_version": "promati.orchestrator.task_relevance_presenter.cp11.v1", "evaluated": True, "authoritative": True, "public_answer_replaced": True, "reason": "presented_covered_relevant_tasks"},
        "task_concise_composer_cp12": {"contract_version": "promati.orchestrator.task_concise_composer.cp12.v1", "evaluated": True, "authoritative": True, "public_answer_replaced": True, "reason": "answer_normalized"},
        "task_research_semantics_cp13": {"contract_version": "promati.orchestrator.task_research_semantics.cp13.v1", "evaluated": True, "authority_scope": "intent_task_research_eligibility_only", "legacy_generic_research_allowed": False, "public_answer_authority": False, "explicit_research_requested": False, "allowed_task_ids": [], "reason": "no_task_research_allowed"},
        "task_public_composition_authority_p4_6f": {"authoritative": True, "public_answer_authority": True, "public_answer_replaced": True, "blocked": False, "reason": "presented_covered_relevant_tasks"},
    }


def test_cp15_missing_gate_input_fails_closed():
    gate = build_release_gate_cp15(None, {})
    assert gate["release_allowed"] is False
    assert "cp8" in gate["blocked_gate_ids"]
    assert "cp9" in gate["blocked_gate_ids"]


def test_cp15_cp10_missing_required_tasks_blocks_release():
    pipeline = _green_pipeline()
    pipeline["task_authority_gate_cp9"].update(blocked=True, reason="missing_required_tasks")
    pipeline["task_coverage_gate_cp10"].update(blocked=True, authoritative=False, reason="missing_required_tasks")
    gate = build_release_gate_cp15(_shadow(["task_org"]), pipeline)
    assert gate["release_allowed"] is False
    assert "cp10" in gate["blocked_gate_ids"]
    assert gate["counts"]["missing"] == 1


def test_cp15_explicit_research_empty_allowlist_cannot_shortcut_release():
    pipeline = _green_pipeline()
    pipeline["task_research_semantics_cp13"]["explicit_research_requested"] = True
    gate = build_release_gate_cp15(_shadow(), pipeline)
    assert gate["release_allowed"] is False
    assert gate["public_authoritative"] is False
    assert "cp13_explicit_research_without_allowed_tasks" in gate["blocking_reasons"]


def test_cp15_m5_exposes_missing_product_and_incomplete_research_chain():
    pipeline = _green_pipeline()
    pipeline["task_authority_gate_cp9"].update(
        blocked=True, reason="missing_required_tasks"
    )
    pipeline["task_coverage_gate_cp10"].update(
        blocked=True, authoritative=False, coverage_complete=False,
        reason="missing_required_tasks",
    )
    pipeline["task_presenter_cp11"].update(
        authoritative=False, public_answer_replaced=False,
        reason="missing_required_tasks",
    )
    pipeline["task_concise_composer_cp12"].update(
        authoritative=False, public_answer_replaced=False,
        reason="missing_required_tasks",
    )
    pipeline["task_public_composition_authority_p4_6f"].update(
        authoritative=False, public_answer_authority=False,
        public_answer_replaced=False, blocked=True,
        reason="missing_required_tasks",
    )
    pipeline["task_research_semantics_cp13"].update(
        explicit_research_requested=True, allowed_task_ids=[],
        reason="no_eligible_research_tasks",
    )
    gate = build_release_gate_cp15(_shadow(["task_product"]), pipeline)

    assert gate["release_allowed"] is False
    assert gate["research"]["explicit_requested"] is True
    assert gate["gate_status"]["cp8"]["missing_required_tasks"] == [
        "task_product"
    ]
    assert {"cp8", "cp10", "cp13", "cp14_d2", "cp14_e3"}.issubset(
        gate["blocked_gate_ids"]
    )


def test_cp15_d2_without_e1_e2_e3_is_not_authoritative():
    pipeline = _green_pipeline()
    pipeline["task_research_semantics_cp13"]["allowed_task_ids"] = ["task_technical"]
    pipeline["task_research_execution_authority_p4_6d2"] = {"authoritative": True, "authority_scope": "intent_task_research_execution_only", "reason": "executed"}
    for key in (
        "task_research_evidence_authority_p4_6e1",
        "task_grounded_synthesis_authority_p4_6e2",
        "task_grounded_synthesis_coverage_authority_p4_6e3",
    ):
        pipeline[key] = {"authoritative": False, "reason": "incomplete"}
    gate = build_release_gate_cp15(_shadow(), pipeline)
    assert gate["release_allowed"] is False
    assert gate["gate_status"]["cp14_d2"]["passed"] is True
    assert {"cp14_e1", "cp14_e2", "cp14_e3"}.issubset(gate["blocked_gate_ids"])


def test_cp15_complete_synthetic_gate_set_is_green():
    pipeline = _green_pipeline()
    # Normal existing-evidence answers can carry inactive CP14 diagnostics;
    # their mere presence must not manufacture a research requirement.
    pipeline["task_research_execution_authority_p4_6d2"] = {
        "authoritative": False, "reason": "no_eligible_research_execution_units"
    }
    gate = build_release_gate_cp15(_shadow(), pipeline)
    assert gate["release_allowed"] is True
    assert gate["public_authoritative"] is True
    assert gate["blocked_gate_ids"] == []
    assert gate["counts"] == {"required": 2, "planned": 2, "executed": 2, "missing": 0, "covered": 2}


def test_cp15_debug_contract_is_filtered_from_compact_response():
    compact = compact_orchestrator_response({
        "status": "ok", "answer": "Kort antwoord.",
        "query_plan": {"domains": ["technical"], "intent_tasks": []},
        "results": [], "evidence_pipeline": {"release_gate_cp15": {"blocking_reasons": ["raw"]}},
    })
    assert compact["answer"] == "Kort antwoord."
    assert "evidence_pipeline" not in compact
    assert "release_gate_cp15" not in compact


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp15_") and callable(value):
            value()
    print("CP15 direct tests passed")
