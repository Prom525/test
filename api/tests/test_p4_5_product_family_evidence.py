
from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.orchestrator.product_family_evidence as family_evidence
from app.orchestrator.complexity import (
    assess_research_requirement,
)
from app.orchestrator.evidence_assessor import (
    RequirementAssessmentStatus,
)
from app.orchestrator.evidence_requirement_catalog import (
    get_requirement_set,
)
from app.orchestrator.planner import (
    build_execution_plan,
)
from app.orchestrator.routing_sanity import (
    apply_routing_sanity,
)
from app.orchestrator.understanding import (
    understand_query,
)


def planned(
    question: str,
):
    plan = understand_query(
        question
    )

    plan = apply_routing_sanity(
        plan
    )

    plan = assess_research_requirement(
        plan
    )

    return build_execution_plan(
        plan
    )


def test_product_selection_maps_to_product_record_requirement():
    requirement_set = (
        get_requirement_set(
            "product_selection"
        )
    )

    assert requirement_set is not None

    assert (
        requirement_set.requirement_set_id
        == "product_lookup.v1"
    )

    assert [
        item.requirement_id
        for item
        in requirement_set.requirements
    ] == [
        "PRODUCT_RECORD",
    ]


def test_advantages_maps_to_product_record_requirement():
    requirement_set = (
        get_requirement_set(
            "advantages_disadvantages"
        )
    )

    assert requirement_set is not None

    assert (
        requirement_set.requirement_set_id
        == "product_lookup.v1"
    )


def test_price_and_inventory_advance_to_price_stock_in_b5():
    for intent in ("inventory_lookup", "price_lookup"):
        requirement_set = get_requirement_set(intent)
        assert requirement_set is not None
        assert requirement_set.requirement_set_id == "price_stock.v1"


def test_family_coverage_assesses_each_family_independently(
    monkeypatch,
):
    plan = planned(
        "Vergelijk TPH HD, BB-U en Proload"
    )

    requirement_set = (
        get_requirement_set(
            "product_selection"
        )
    )

    calls = []

    def fake_assess(
        requirement_set,
        evidence_items,
        *,
        target_entity_ids=None,
        now=None,
    ):
        family_code = (
            target_entity_ids[
                "product"
            ]
        )

        calls.append(
            family_code
        )

        satisfied = (
            family_code
            in {
                "PROM-TPH-HD",
                "BB-U",
            }
        )

        return SimpleNamespace(
            requirement_results=(
                SimpleNamespace(
                    requirement_id=(
                        "PRODUCT_RECORD"
                    ),
                    status=(
                        RequirementAssessmentStatus
                        .SATISFIED
                        if satisfied
                        else RequirementAssessmentStatus
                        .MISSING
                    ),
                    matched_evidence_ids=(
                        (
                            "evidence-"
                            + family_code
                        ),
                    )
                    if satisfied
                    else (),
                    reasons=(
                        ()
                        if satisfied
                        else (
                            "missing_evidence",
                        )
                    ),
                ),
            ),
        )

    monkeypatch.setattr(
        family_evidence,
        "assess_evidence",
        fake_assess,
    )

    coverage = (
        family_evidence
        .assess_product_family_coverage(
            requirement_set,
            (),
            plan,
            now=SimpleNamespace(),
        )
    )

    assert calls == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
    ]

    assert (
        coverage[
            "missing_family_codes"
        ]
        == [
            "PROLOAD",
        ]
    )

    assert (
        coverage[
            "all_satisfied"
        ]
        is False
    )


def test_recovery_only_executes_requested_missing_family():
    plan = planned(
        "Vergelijk TPH HD, BB-U en Proload"
    )

    calls = []

    def sender(
        path,
        payload,
    ):
        calls.append(
            (
                path,
                dict(payload),
            )
        )

        return {
            "status": "ok",
            "detected_family_code":
                payload[
                    "family_code"
                ],
            "family_context": {
                "status": "ok",
                "results": [],
            },
        }

    raw, metadata = (
        family_evidence
        .recover_missing_product_families(
            plan,
            (
                "PROLOAD",
            ),
            sender=sender,
        )
    )

    assert len(calls) == 1

    assert (
        calls[0][0]
        == "/product/assistant/ask"
    )

    assert (
        calls[0][1][
            "family_code"
        ]
        == "PROLOAD"
    )

    assert (
        calls[0][1][
            "vraag"
        ]
        == (
            "Vergelijk TPH HD, "
            "BB-U en Proload"
        )
    )

    assert metadata[
        "attempted_family_codes"
    ] == [
        "PROLOAD",
    ]

    assert (
        metadata[
            "attempted_call_count"
        ]
        == 1
    )

    assert len(raw) == 1


def test_four_product_recovery_respects_total_specialist_budget():
    plan = planned(
        "Beoordeel dit concept met "
        "TPH HD, Belle Banne U, "
        "Proload en Impact Bars"
    )

    assert (
        len(
            plan.execution_steps
        )
        == 4
    )

    calls = []

    def sender(
        path,
        payload,
    ):
        calls.append(
            dict(payload)
        )

        return {
            "status": "ok",
            "family_context": {
                "status": "ok",
                "results": [],
            },
        }

    _raw, metadata = (
        family_evidence
        .recover_missing_product_families(
            plan,
            (
                "PROM-TPH-HD",
                "BB-U",
                "PROLOAD",
                "IMPACT-BARS",
            ),
            sender=sender,
        )
    )

    # Hard total = 6. Initial fan-out = 4.
    # Er mogen dus maximaal 2 recoveries volgen.
    assert len(calls) == 2

    assert (
        metadata[
            "attempted_call_count"
        ]
        == 2
    )

    assert (
        metadata[
            "skipped_budget_family_codes"
        ]
        == [
            "PROLOAD",
            "IMPACT-BARS",
        ]
    )


def test_recovery_never_changes_to_another_specialist_action():
    plan = planned(
        "Vergelijk Proload en Impact Bars "
        "voor deze toepassing"
    )

    paths = []

    def sender(
        path,
        payload,
    ):
        paths.append(
            path
        )

        return {
            "status": "ok",
            "family_context": {
                "status": "ok",
                "results": [],
            },
        }

    family_evidence.recover_missing_product_families(
        plan,
        (
            "PROLOAD",
            "IMPACT-BARS",
        ),
        sender=sender,
    )

    assert paths

    assert set(
        paths
    ) == {
        "/product/assistant/ask",
    }


def test_service_wires_family_coverage_before_generic_research():
    from pathlib import Path

    service = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "app"
        / "orchestrator"
        / "service.py"
    )

    source = service.read_text(
        encoding="utf-8-sig",
    )
    stage = (
        service.parent / "product_family_recovery_stage.py"
    ).read_text(encoding="utf-8-sig")

    coverage_position = (
        stage.index(
            "assess_product_family_coverage("
        )
    )

    recovery_position = (
        stage.index(
            "recover_missing_product_families("
        )
    )

    stage_position = source.index(
        "run_product_family_recovery_stage("
    )
    generic_gate_position = (
        source.index(
            "decide_research_requirement,",
            stage_position,
        )
    )

    assert coverage_position < recovery_position
    assert stage_position < generic_gate_position

    assert (
        "working_evidence_items"
        in source
    )
