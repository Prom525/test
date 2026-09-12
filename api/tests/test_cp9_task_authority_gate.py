from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_authority_gate import (
    guard_public_composition_authority,
    guard_public_composition_canary,
)


def _composition(*, authoritative=True):
    return {
        "authoritative": authoritative,
        "public_answer_authority": authoritative,
        "public_answer_replaced": authoritative,
        "reason": "activated_public_multi_intent_composition_authority",
    }


def _shadow(missing):
    return {
        "summary": {
            "required_total": 2,
            "required_planned": 2 - len(missing),
            "required_executed": 2 - len(missing),
            "required_missing": len(missing),
            "missing_required_tasks": missing,
        },
        "tasks": [{"task_id": task_id} for task_id in missing],
    }


def test_cp9_missing_required_task_revokes_public_authority_and_answer():
    answer, authority, gate = guard_public_composition_authority(
        "composed", "legacy", _composition(), _shadow(["task_org_1"])
    )

    assert answer == "legacy"
    assert authority["authoritative"] is False
    assert authority["public_answer_authority"] is False
    assert authority["public_answer_replaced"] is False
    assert authority["blocked"] is True
    assert authority["reason"] == "missing_required_tasks"
    assert authority["missing_required_tasks"] == ["task_org_1"]
    assert gate["blocked"] is True


def test_cp9_complete_execution_preserves_composition_authority():
    answer, authority, gate = guard_public_composition_authority(
        "composed", "legacy", _composition(), _shadow([])
    )

    assert answer == "composed"
    assert authority["authoritative"] is True
    assert authority["public_answer_authority"] is True
    assert gate["blocked"] is False


def test_cp9_missing_shadow_fails_closed():
    answer, authority, gate = guard_public_composition_authority(
        "composed", "legacy", _composition(), None
    )

    assert answer == "legacy"
    assert authority["authoritative"] is False
    assert authority["reason"] == "task_execution_shadow_unavailable"
    assert gate["blocked"] is True


def test_cp9_inconsistent_shadow_fails_closed():
    inconsistent = _shadow([])
    inconsistent["summary"]["required_missing"] = 1
    answer, authority, gate = guard_public_composition_authority(
        "composed", "legacy", _composition(), inconsistent
    )

    assert answer == "legacy"
    assert authority["authoritative"] is False
    assert authority["reason"] == "task_execution_shadow_unavailable"
    assert gate["task_execution_shadow_available"] is False


def test_cp9_missing_task_also_revokes_earlier_public_canary():
    _answer, _authority, gate = guard_public_composition_authority(
        "composed", "legacy", _composition(), _shadow(["task_org_1"])
    )
    public_canary = guard_public_composition_canary(
        {"activated": True, "public_answer_replaced": True}, gate
    )

    assert public_canary["activated"] is False
    assert public_canary["authoritative"] is False
    assert public_canary["public_answer_replaced"] is False
    assert public_canary["reason"] == "missing_required_tasks"


def test_cp9_compact_response_exposes_only_cp8_summary():
    shadow = _shadow(["task_org_1"])
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": "legacy",
        "query_plan": {"domains": ["diagnostics", "org"]},
        "results": [],
        "task_execution_shadow": shadow,
        "evidence_pipeline": {
            "task_authority_gate_cp9": {"tasks": ["large-debug-row"]}
        },
    })

    assert compact["task_execution_shadow_summary"]["required_missing"] == 1
    assert compact["task_execution_shadow_summary"]["missing_required_tasks"] == [
        "task_org_1"
    ]
    assert "evidence_pipeline" not in compact
    assert "task_execution_shadow" not in compact
