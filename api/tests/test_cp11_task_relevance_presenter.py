from app.orchestrator.models import Domain, IntentTask, QueryPlan
from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_relevance_presenter import present_relevant_task_answer


def _plan(tasks, excluded=()):
    return QueryPlan(
        original_question="test",
        normalized_question="test",
        intent_tasks=tasks,
        excluded_domains=list(excluded),
        multi_intent=len(tasks) > 1,
    )


def _task(task_id, domain, *, required=True, polarity="requested"):
    return IntentTask(
        task_id=task_id, domain=domain, intent=f"{domain.value}_lookup",
        required=required, polarity=polarity,
    )


def _unit(task_id, domain, text, evidence_id):
    return {
        "task_id": task_id, "domain": domain.value, "status": "grounded",
        "claims": [{"text": text, "evidence_ids": [evidence_id]}],
        "evidence_ids_used": [evidence_id],
    }


def _gate(blocked=False, reason="required_execution_and_coverage_authoritative"):
    return {"blocked": blocked, "authoritative": not blocked, "reason": reason}


def test_cp11_s3_presents_only_technical_and_records_excluded_domains():
    plan = _plan(
        [_task("task_1_technical", Domain.TECHNICAL)],
        [Domain.PRODUCT, Domain.INSPECTION, Domain.ORG, Domain.RFQ],
    )
    answer, status, authority = present_relevant_task_answer(
        plan, "legacy", _gate(),
        {"units": [_unit("task_1_technical", Domain.TECHNICAL, "CEMA uitleg", "e-tech")]},
    )

    assert answer == "Technische informatie:\n- CEMA uitleg"
    assert status["included_task_ids"] == ["task_1_technical"]
    assert status["excluded_domains"] == ["inspection", "org", "product", "rfq"]
    assert authority["public_answer_replaced"] is True


def test_cp11_m3_filters_excluded_and_unrequested_task_units():
    tasks = [
        _task("task_product", Domain.PRODUCT),
        _task("task_technical", Domain.TECHNICAL),
        _task("task_org", Domain.ORG, polarity="excluded"),
    ]
    coverage = {"units": [
        _unit("task_product", Domain.PRODUCT, "Belle Banne U voor 1200 mm", "e-product"),
        _unit("task_technical", Domain.TECHNICAL, "CEMA-limiet", "e-tech"),
        _unit("task_org", Domain.ORG, "Irrelevante organisatie", "e-org"),
        _unit("unknown", Domain.INSPECTION, "Irrelevante inspectie", "e-inspection"),
    ]}
    answer, status, _authority = present_relevant_task_answer(
        _plan(tasks, [Domain.INSPECTION, Domain.ORG]), "legacy", _gate(), coverage
    )

    assert "Belle Banne U voor 1200 mm" in answer
    assert "CEMA-limiet" in answer
    assert "organisatie" not in answer.casefold()
    assert "inspectie" not in answer.casefold()
    assert status["excluded_task_ids"] == ["task_org"]
    assert status["excluded_evidence_ids"] == ["e-inspection", "e-org"]


def test_cp11_cp10_blocked_preserves_legacy_and_revokes_authority():
    answer, status, authority = present_relevant_task_answer(
        _plan([_task("task_org", Domain.ORG)]),
        "legacy", _gate(True, "missing_required_tasks"),
        {"units": [_unit("task_org", Domain.ORG, "org", "e-org")]},
        None,
    )

    assert answer == "legacy"
    assert status["evaluated"] is True
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False
    assert status["reason"] == "missing_required_tasks"
    assert status["missing_required_tasks"] == []
    assert status["included_task_ids"] == []
    assert status["task_decisions"] == [{
        "task_id": "task_org", "domain": "org", "included": False,
        "reason": "missing_required_tasks",
    }]
    assert authority["reason"] == "missing_required_tasks"
    assert authority["public_answer_replaced"] is False


def test_cp11_blocked_propagates_missing_tasks_without_composition_authority():
    gate = _gate(True, "missing_required_tasks")
    gate["missing_required_tasks"] = ["task_2_org"]
    answer, status, authority = present_relevant_task_answer(
        _plan([_task("task_2_org", Domain.ORG)]),
        "legacy diagnostics", gate, None, None,
    )

    assert answer == "legacy diagnostics"
    assert status["reason"] == "missing_required_tasks"
    assert status["missing_required_tasks"] == ["task_2_org"]
    assert authority["task_presenter_cp11"] == status
    assert authority["authoritative"] is False
    assert authority["public_answer_replaced"] is False


def test_cp11_structured_raw_evidence_fails_closed_to_legacy_answer():
    raw = (
        'latest_position_measurement: {"document_date": "2026-05-27", '
        '"measurement_count": 4, "min_meshoogte_mm": 3.0, '
        '"max_meshoogte_mm": 6.0, '
        '"related_subject": "latest_blade_height:"}'
    )
    golden = (
        "MV1 / Mengveld 1 - directe aandacht nodig.\n"
        "Laatste inspectie: 2026-05-27.\n"
        "Meetbeeld: 4 posities, minimum meshhoogte 3.0 mm, maximum 6.0 mm.\n"
        "Onderhoudsprioriteit: direct actie nemen."
    )
    answer, status, authority = present_relevant_task_answer(
        _plan([_task("task_inspection", Domain.INSPECTION)]),
        golden, _gate(),
        {"units": [_unit("task_inspection", Domain.INSPECTION, raw, "e-inspection")]},
        None,
    )

    assert answer == golden
    assert len(answer) < 1_200
    for expected in ("2026-05-27", "4 posities", "3.0 mm", "6.0 mm"):
        assert expected in answer
    assert "latest_position_measurement:" not in answer
    assert "latest_blade_height:" not in answer
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False
    assert authority["public_answer_replaced"] is False


def test_cp11_requested_task_without_covered_unit_fails_closed():
    answer, status, authority = present_relevant_task_answer(
        _plan([_task("task_rfq", Domain.RFQ), _task("task_product", Domain.PRODUCT)]),
        "legacy", _gate(),
        {"units": [_unit("task_rfq", Domain.RFQ, "RFQ ready", "e-rfq")]},
    )

    assert answer == "legacy"
    assert status["reason"] == "not_covered"
    assert status["excluded_task_ids"] == ["task_product"]
    assert authority["public_answer_replaced"] is False


def test_cp11_compact_omits_presenter_debug():
    compact = compact_orchestrator_response({
        "status": "ok", "answer": "small", "query_plan": {"domains": ["rfq"]},
        "results": [], "evidence_pipeline": {
            "task_presenter_cp11": {"task_decisions": ["large"] * 100}
        },
    })
    assert "task_presenter_cp11" not in compact
    assert "evidence_pipeline" not in compact


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp11_") and callable(value):
            value()
    print("CP11 direct tests passed")
