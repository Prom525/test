
from __future__ import annotations

import ast
from pathlib import Path

from app.orchestrator.complexity import (
    assess_research_requirement,
)
from app.orchestrator.models import (
    Domain,
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

    plan = (
        assess_research_requirement(
            plan
        )
    )

    return build_execution_plan(
        plan
    )


def values(plan):
    return [
        str(item.value)
        for item
        in plan.product_families
    ]


def product_steps(plan):
    return [
        step
        for step
        in plan.execution_steps
        if step.action
        == "product_assistant"
    ]


def test_three_product_comparison_removes_false_org_and_enables_research():
    plan = planned(
        "Vergelijk TPH HD, BB-U en Proload"
    )

    assert values(plan) == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
    ]

    assert Domain.ORG not in (
        plan.domains
    )

    assert all(
        step.action
        != "org_assistant"
        for step
        in plan.execution_steps
    )

    assert [
        step.params["family_code"]
        for step
        in product_steps(plan)
    ] == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
    ]

    assert (
        plan.research_required
        is True
    )

    assert (
        "multiple_product_families"
        in plan.complexity_reasons
    )

    assert (
        "multi_product_engineering"
        in plan.complexity_reasons
    )


def test_four_product_project_removes_false_org_and_enables_research():
    question = (
        "Beoordeel dit Umicore-concept "
        "met TPH HD, Belle Banne U, "
        "Proload en Impact Bars"
    )

    plan = planned(
        question
    )

    assert values(plan) == [
        "PROM-TPH-HD",
        "BB-U",
        "PROLOAD",
        "IMPACT-BARS",
    ]

    assert Domain.ORG not in (
        plan.domains
    )

    assert not any(
        step.action
        == "org_assistant"
        for step
        in plan.execution_steps
    )

    assert len(
        product_steps(plan)
    ) == 4

    assert (
        plan.research_required
        is True
    )

    assert (
        "multi_product_engineering"
        in plan.complexity_reasons
    )


def test_proload_impact_bars_selection_enables_research():
    plan = planned(
        "Vergelijk Proload en Impact Bars "
        "voor deze toepassing"
    )

    assert values(plan) == [
        "PROLOAD",
        "IMPACT-BARS",
    ]

    assert Domain.ORG not in (
        plan.domains
    )

    assert (
        plan.research_required
        is True
    )


def test_routing_sanity_is_noop_for_legacy_minimal_plan_stub():
    class LegacyPlanStub:
        def __init__(self):
            self.intent = "diagnostics"
            self.clarification_required = False
            self.execution_steps = []
            self.research_required = True
            self.requested_information = []

    plan = LegacyPlanStub()

    corrected = (
        apply_routing_sanity(
            plan
        )
    )

    assert corrected is plan
    assert (
        corrected.intent
        == "diagnostics"
    )


def test_single_product_does_not_get_multi_product_trigger():
    plan = planned(
        "Geef productinformatie "
        "over TPH HD"
    )

    assert values(plan) == [
        "PROM-TPH-HD",
    ]

    assert (
        "multiple_product_families"
        not in plan.complexity_reasons
    )

    assert (
        "multi_product_engineering"
        not in plan.complexity_reasons
    )


def test_real_org_question_remains_org():
    plan = planned(
        "Wie is verantwoordelijk "
        "voor HR bij Promati?"
    )

    assert (
        plan.primary_domain
        == Domain.ORG
    )

    assert (
        plan.intent
        == "org_lookup"
    )

    assert any(
        step.action
        == "org_assistant"
        for step
        in plan.execution_steps
    )


def test_existing_system_meta_diagnostics_route_is_unchanged():
    plan = planned(
        "Welke specialist gebruikt "
        "de orchestrator voor productvragen?"
    )

    assert (
        plan.primary_domain
        == Domain.DIAGNOSTICS
    )

    assert (
        plan.intent
        == "diagnostics_overview"
    )

    assert [
        step.action
        for step
        in plan.execution_steps
    ] == [
        "diagnostics_assistant",
    ]


def test_inspection_pipeline_diagnostics_is_unchanged():
    plan = planned(
        "Geef een diagnose van "
        "de inspection pipeline"
    )

    assert (
        plan.primary_domain
        == Domain.DIAGNOSTICS
    )

    assert (
        plan.intent
        == "diagnostics_inspection_pipeline"
    )


def test_system_meta_org_mismatch_is_repaired_before_planning():
    plan = understand_query(
        "Welke specialist gebruikt "
        "de orchestrator voor productvragen?"
    )

    # Simuleer de oorspronkelijke failure class:
    # classifier = system_meta, maar business/org route.
    plan.primary_domain = (
        Domain.ORG
    )

    plan.domains = [
        Domain.ORG,
    ]

    plan.intent = (
        "org_lookup"
    )

    plan.execution_steps = []

    corrected = (
        apply_routing_sanity(
            plan
        )
    )

    assert (
        corrected.primary_domain
        == Domain.DIAGNOSTICS
    )

    assert (
        corrected.domains
        == [
            Domain.DIAGNOSTICS,
        ]
    )

    assert corrected.intent.startswith(
        "diagnostics_"
    )

    corrected = (
        assess_research_requirement(
            corrected
        )
    )

    corrected = (
        build_execution_plan(
            corrected
        )
    )

    assert all(
        step.action
        != "org_assistant"
        for step
        in corrected.execution_steps
    )

    assert any(
        step.action
        == "diagnostics_assistant"
        for step
        in corrected.execution_steps
    )


def test_explicit_org_intent_is_not_removed_from_multi_product_query():
    plan = understand_query(
        "Vergelijk TPH HD en BB-U "
        "en wie is verantwoordelijk "
        "voor productbeheer?"
    )

    if Domain.ORG not in plan.domains:
        plan.domains.append(
            Domain.ORG
        )

    corrected = (
        apply_routing_sanity(
            plan
        )
    )

    assert (
        Domain.ORG
        in corrected.domains
    )


def test_service_places_routing_sanity_immediately_after_understanding():
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

    tree = ast.parse(
        source
    )

    run_node = next(
        node
        for node
        in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name
        == "run_orchestrator"
    )

    def name(node):
        if isinstance(
            node,
            ast.Name,
        ):
            return node.id

        if isinstance(
            node,
            ast.Attribute,
        ):
            return node.attr

        return None

    events = []

    for node in ast.walk(
        run_node
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not any(
            isinstance(
                target,
                ast.Name,
            )
            and target.id
            == "plan"
            for target
            in node.targets
        ):
            continue

        call = node.value

        if not isinstance(
            call,
            ast.Call,
        ):
            continue

        call_name = name(
            call.func
        )

        if (
            call_name
            == "apply_routing_sanity"
        ):

            events.append(
                (
                    node.lineno,
                    "apply_routing_sanity",
                    "direct",
                )
            )

            continue

        if (
            call_name
            != "_observability_call"
        ):

            continue

        args = (
            call.args
            or []
        )

        if len(args) < 3:
            continue

        callable_name = name(
            args[2]
        )

        phase_name = None

        if (
            len(args) >= 2
            and isinstance(
                args[1],
                ast.Constant,
            )
        ):

            phase_name = (
                args[1].value
            )

        if callable_name in {
            "understand_query",
            "assess_research_requirement",
            "build_execution_plan",
        }:

            events.append(
                (
                    node.lineno,
                    callable_name,
                    phase_name,
                )
            )

    ordered = [
        (
            callable_name,
            phase_name,
        )
        for (
            _line,
            callable_name,
            phase_name,
        )
        in sorted(
            events
        )
    ]

    assert ordered[:4] == [
        (
            "understand_query",
            "understanding",
        ),
        (
            "apply_routing_sanity",
            "direct",
        ),
        (
            "assess_research_requirement",
            "research_requirement",
        ),
        (
            "build_execution_plan",
            "planning",
        ),
    ]

    # P3 observability contract blijft stabiel:
    # routing_sanity krijgt geen nieuwe timings_ms key.
    assert (
        '"routing_sanity",'
        not in source
    )
