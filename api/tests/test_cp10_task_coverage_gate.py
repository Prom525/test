from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_authority_gate import (
    build_task_coverage_gate_status,
    guard_task_coverage_authority,
)


def _shadow(missing=()):
    missing = list(missing)
    return {
        "summary": {
            "required_missing": len(missing),
            "missing_required_tasks": missing,
        }
    }


def _coverage(*, authoritative=True, complete=True, reason="covered"):
    return {
        "authoritative": authoritative,
        "authority_scope": "intent_task_grounded_synthesis_coverage_only",
        "complete_task_coverage": complete,
        "public_answer_authority": False,
        "reason": reason,
    }


def test_cp10_missing_required_tasks_are_explicit_and_revoke_authority():
    gate = build_task_coverage_gate_status(
        _shadow(["task_2_org"]), _coverage()
    )
    answer, authority = guard_task_coverage_authority(
        "composed",
        "legacy",
        {"authoritative": True, "public_answer_replaced": True},
        gate,
    )

    assert gate["blocked"] is True
    assert gate["authoritative"] is False
    assert gate["reason"] == "missing_required_tasks"
    assert gate["missing_required_tasks"] == ["task_2_org"]
    assert answer == "legacy"
    assert authority["authoritative"] is False
    assert authority["public_answer_replaced"] is False


def test_cp10_covered_execution_reports_coverage_block_reason():
    gate = build_task_coverage_gate_status(
        _shadow(), _coverage(authoritative=False, reason="insufficient_evidence")
    )

    assert gate["required_task_execution_covered"] is True
    assert gate["missing_required_tasks"] == []
    assert gate["blocked"] is True
    assert gate["reason"] == "coverage_not_authoritative"
    assert gate["coverage_reason"] == "insufficient_evidence"


def test_cp10_missing_coverage_is_visible_even_without_composition():
    gate = build_task_coverage_gate_status(_shadow(), None)

    assert gate["evaluated"] is True
    assert gate["required_task_execution_covered"] is True
    assert gate["coverage_available"] is False
    assert gate["blocked"] is True
    assert gate["reason"] == "coverage_unavailable"


def test_cp10_authority_requires_execution_and_authoritative_coverage():
    gate = build_task_coverage_gate_status(_shadow(), _coverage())
    answer, authority = guard_task_coverage_authority(
        "composed", "legacy", {"authoritative": True}, gate
    )

    assert gate["blocked"] is False
    assert gate["authoritative"] is True
    assert gate["required_task_execution_covered"] is True
    assert gate["coverage_authoritative"] is True
    assert answer == "composed"
    assert authority["authoritative"] is True


def test_cp10_compact_omits_full_gate_debug_object():
    compact = compact_orchestrator_response(
        {
            "status": "ok",
            "answer": "legacy",
            "query_plan": {"domains": ["org"]},
            "results": [],
            "task_execution_shadow": _shadow(["task_2_org"]),
            "evidence_pipeline": {
                "task_coverage_gate_cp10": {"large": ["debug"] * 100}
            },
        }
    )

    assert "evidence_pipeline" not in compact
    assert "task_coverage_gate_cp10" not in compact
    assert compact["task_execution_shadow_summary"]["required_missing"] == 1


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp10_") and callable(value):
            value()
    print("CP10 direct tests passed")
