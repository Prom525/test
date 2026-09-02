from __future__ import annotations

from app.orchestrator.planner import (
    build_execution_plan,
)
from app.orchestrator.specialist_registry import (
    SPECIALIST_CONTRACTS,
)
from app.orchestrator.understanding import (
    detect_product_families,
    understand_query,
)


def codes(plan) -> list[str]:
    return [
        str(item.value)
        for item in plan.product_families
    ]


def product_steps(plan):
    return [
        step
        for step in plan.execution_steps
        if step.action == "product_assistant"
    ]


def planned(question: str):
    return build_execution_plan(
        understand_query(question)
    )


def test_single_tph_keeps_legacy_family_code():
    plan = planned(
        "Geef productinformatie over TPH HD"
    )

    assert codes(plan) == [
        "PROM-TPH-HD",
    ]

    assert (
        plan.entities["family_code"].value
        == "PROM-TPH-HD"
    )

    steps = product_steps(plan)

    assert len(steps) == 1
    assert (
        steps[0].step_id
        == "step_1_product"
    )
    assert (
        steps[0].params["family_code"]
        == "PROM-TPH-HD"
    )


def test_single_bb_u_keeps_width_behavior():
    plan = planned(
        "Welke BB-U voor 1000 mm?"
    )

    assert codes(plan) == [
        "BB-U",
    ]

    assert (
        plan.entities["family_code"].value
        == "BB-U"
    )

    assert (
        plan.entities["belt_width_mm"].value
        == 1000
    )

    steps = product_steps(plan)

    assert len(steps) == 1
    assert (
        steps[0].params["family_code"]
        == "BB-U"
    )
    assert (
        steps[0].params["belt_width_mm"]
        == 1000
    )


def test_multi_family_preserves_mention_order():
    plan = planned(
        "Vergelijk TPH HD, BB-U en Proload"
    )

    assert codes(plan) == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
    ]

    assert (
        "family_code"
        not in plan.entities
    )

    steps = product_steps(plan)

    assert [
        step.params["family_code"]
        for step in steps
    ] == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
    ]

    assert [
        step.step_id
        for step in steps
    ] == [
        "step_1_product_PROM-TPH-HD",
        "step_2_product_BB-U",
        "step_3_product_PROLOAD",
    ]


def test_proload_and_impact_bars_are_both_detected():
    question = (
        "Vergelijk Proload en Impact Bars "
        "voor deze toepassing"
    )

    plan = planned(
        question
    )

    assert codes(plan) == [
        "PROLOAD",
        "IMPACT-BARS",
    ]

    assert (
        "family_code"
        not in plan.entities
    )

    steps = product_steps(plan)

    assert [
        step.params["family_code"]
        for step in steps
    ] == [
        "PROLOAD",
        "IMPACT-BARS",
    ]

    assert all(
        step.params["vraag"] == question
        for step in steps
    )


def test_four_family_concept_fans_out_four_product_calls():
    question = (
        "Beoordeel dit Umicore-concept met "
        "TPH HD, Belle Banne U, Proload "
        "en Impact Bars"
    )

    plan = planned(
        question
    )

    assert codes(plan) == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
        "IMPACT-BARS",
    ]

    steps = product_steps(plan)

    assert len(steps) == 4

    assert [
        step.params["family_code"]
        for step in steps
    ] == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
        "IMPACT-BARS",
    ]

    assert all(
        step.action
        == "product_assistant"
        for step in steps
    )

    assert all(
        step.params["vraag"] == question
        for step in steps
    )


def test_repeated_family_is_deduplicated():
    detected = detect_product_families(
        "TPH HD vergelijken met TPH-HD "
        "en BB-U"
    )

    assert [
        str(item.value)
        for item in detected
    ] == [
        "PROM-TPH-HD",
        "BB-U",
    ]


def test_impact_bars_alone_keeps_singular_compatibility():
    plan = planned(
        "Geef productinformatie over Impact Bars"
    )

    assert codes(plan) == [
        "IMPACT-BARS",
    ]

    assert (
        plan.entities["family_code"].value
        == "IMPACT-BARS"
    )

    steps = product_steps(plan)

    assert len(steps) == 1

    assert (
        steps[0].params["family_code"]
        == "IMPACT-BARS"
    )


def test_contextual_bb_u_fallback_remains_available():
    plan = planned(
        "Wat zijn de voordelen van U 1800?"
    )

    assert codes(plan) == [
        "BB-U",
    ]

    assert (
        plan.entities["family_code"].value
        == "BB-U"
    )


def test_product_planner_fields_are_allowlisted():
    contract = SPECIALIST_CONTRACTS[
        "product_assistant"
    ]

    planner_fields = set(
        contract.planner_fields
    )

    accepted_fields = set(
        contract.accepted_input_fields
    )

    assert {
        "vraag",
        "mode",
        "family_code",
        "belt_width_mm",
    }.issubset(
        planner_fields
    )

    assert planner_fields.issubset(
        accepted_fields
    )
