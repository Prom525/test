from types import SimpleNamespace

from app.orchestrator.evidence_assessor import EvidenceAssessmentStatus
from app.orchestrator.evidence_research_gate import (
    RESEARCH_GATE_CONTRACT_VERSION,
    ResearchGateDecision,
    ResearchGateStatus,
)
from app.orchestrator.models import Domain, IntentTask
from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_research_semantics import (
    build_task_research_semantics,
    gate_legacy_generic_research,
)


def _plan(tasks, excluded=(), clarification=False):
    return SimpleNamespace(
        intent_tasks=tasks,
        excluded_domains=list(excluded),
        clarification_required=clarification,
    )


def _task(task_id, domain, *, required=True, polarity="requested"):
    return IntentTask(
        task_id=task_id,
        domain=domain,
        intent=f"{domain.value}_lookup",
        required=required,
        polarity=polarity,
    )


def _shadow(*tasks):
    return {
        "tasks": [
            {
                "task_id": task.task_id,
                "executed": executed,
                "required": task.required,
                "polarity": task.polarity,
            }
            for task, executed in tasks
        ]
    }


def _authority(*tasks_with_gap):
    return {
        "authoritative": True,
        "authority_scope": "intent_task_research_decision_only",
        "public_answer_authority": False,
        "task_research_decisions": [
            {
                "task_id": task.task_id,
                "research_decision": {
                    "research_required": gap,
                    "target_requirement_ids": [f"{task.task_id}_evidence"] if gap else [],
                },
            }
            for task, gap in tasks_with_gap
        ],
    }


def test_cp13_allows_only_required_requested_executed_gap_tasks():
    technical = _task("task_1_technical", Domain.TECHNICAL)
    optional = _task("task_2_product", Domain.PRODUCT, required=False)
    semantics = build_task_research_semantics(
        _plan([technical, optional]),
        _shadow((technical, True), (optional, True)),
        _authority((technical, True), (optional, True)),
    )

    assert semantics["allowed_task_ids"] == ["task_1_technical"]
    rows = {row["task_id"]: row for row in semantics["tasks"]}
    assert rows["task_1_technical"]["reason"] == "coverage_gap"
    assert rows["task_2_product"]["reason"] == "not_required_task"
    assert semantics["public_answer_authority"] is False


def test_cp13_blocks_excluded_and_negated_domains():
    product = _task("task_product", Domain.PRODUCT)
    inspection = _task("task_inspection", Domain.INSPECTION, polarity="excluded")
    semantics = build_task_research_semantics(
        _plan([product, inspection], excluded=(Domain.PRODUCT, Domain.INSPECTION)),
        _shadow((product, True), (inspection, False)),
        _authority((product, True), (inspection, True)),
    )

    rows = {row["task_id"]: row for row in semantics["tasks"]}
    assert rows["task_product"]["reason"] == "excluded_domain"
    assert rows["task_inspection"]["reason"] == "negated_domain"
    assert semantics["allowed_task_ids"] == []
    assert {row["domain"] for row in semantics["excluded_domain_decisions"]} == {
        "product", "inspection"
    }


def test_cp13_missing_required_execution_cannot_be_repaired_by_research():
    org = _task("task_2_org", Domain.ORG)
    semantics = build_task_research_semantics(
        _plan([org]), _shadow((org, False)), _authority((org, True))
    )

    assert semantics["tasks"][0]["reason"] == "missing_required_execution"
    assert semantics["tasks"][0]["research_allowed"] is False


def test_cp13_clarification_and_sufficient_coverage_block_research():
    technical = _task("task_technical", Domain.TECHNICAL)
    sufficient = build_task_research_semantics(
        _plan([technical]), _shadow((technical, True)), _authority((technical, False))
    )
    clarification = build_task_research_semantics(
        _plan([technical], clarification=True),
        _shadow((technical, True)),
        _authority((technical, True)),
    )

    assert sufficient["tasks"][0]["reason"] == "coverage_already_authoritative"
    assert clarification["tasks"][0]["reason"] == "clarification_required"


def test_cp13_suppresses_generic_research_without_granting_authority():
    technical = _task("task_technical", Domain.TECHNICAL)
    semantics = build_task_research_semantics(
        _plan([technical]), _shadow((technical, True)), _authority((technical, True))
    )
    decision = ResearchGateDecision(
        contract_version=RESEARCH_GATE_CONTRACT_VERSION,
        requirement_set_id="technical.v1",
        intent="technical_lookup",
        status=ResearchGateStatus.REQUIRED,
        research_required=True,
        target_requirement_ids=("technical_evidence",),
        reasons=("assessment_insufficient",),
        assessment_status=EvidenceAssessmentStatus.INSUFFICIENT,
    )
    gated = gate_legacy_generic_research(decision, semantics)

    assert gated.research_required is False
    assert gated.status is ResearchGateStatus.NOT_REQUIRED
    assert semantics["authoritative"] is False
    assert semantics["public_answer_authority"] is False


def test_cp13_debug_contract_is_filtered_from_compact_response():
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": "Kort antwoord.",
        "query_plan": {"domains": ["technical"], "intent_tasks": []},
        "results": [],
        "evidence_pipeline": {
            "task_research_semantics_cp13": {"tasks": [{"raw": "x" * 10000}]}
        },
    })

    assert "evidence_pipeline" not in compact
    assert "task_research_semantics_cp13" not in compact
    assert compact["answer"] == "Kort antwoord."


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp13_") and callable(value):
            value()
    print("CP13 direct tests passed")
