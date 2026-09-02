
from __future__ import annotations

from app.orchestrator.models import (
    DetectedEntity,
    Domain,
    QueryPlan,
)
from app.orchestrator.understanding import (
    detect_diagnostics_depth,
    detect_diagnostics_domain,
    detect_diagnostics_mode,
    detect_diagnostics_score,
    detect_intent,
)


# PROMATI_ROUTING_SANITY_P4_5B3


_EXPLICIT_ORG_SIGNALS = (
    "wie is",
    "wie beheert",
    "wie is verantwoordelijk",
    "verantwoordelijk voor",
    "contactpersoon",
    "organisatie",
    "organigram",
    "afdeling",
    "manager",
    "collega",
    "personeel",
    "hr ",
    " hr",
    "human resources",
    "directeur",
)


def _enum_value(
    value,
) -> str:

    return str(
        getattr(
            value,
            "value",
            value,
        )
        or ""
    ).strip().lower()


def _has_explicit_org_intent(
    question: str,
) -> bool:

    q = (
        question
        or ""
    ).casefold()

    return any(
        signal in q
        for signal
        in _EXPLICIT_ORG_SIGNALS
    )


def _detected_entity(
    name: str,
    value,
    *,
    confidence: float,
) -> DetectedEntity:

    return DetectedEntity(
        name=name,
        raw_value=value,
        value=value,
        confidence=confidence,
        source="routing_sanity",
    )


def _repair_system_meta_route(
    plan: QueryPlan,
) -> QueryPlan:

    q = (
        plan.normalized_question
        or plan.original_question
        or ""
    )

    mode = (
        detect_diagnostics_mode(
            q
        )
    )

    diagnostics_domain = (
        detect_diagnostics_domain(
            q
        )
    )

    depth = (
        detect_diagnostics_depth(
            q,
            mode,
        )
    )

    score = (
        detect_diagnostics_score(
            q
        )
    )

    confidence = max(
        float(
            plan.confidence
            or 0.0
        ),
        float(score),
        0.90,
    )

    plan.primary_domain = (
        Domain.DIAGNOSTICS
    )

    plan.domains = [
        Domain.DIAGNOSTICS,
    ]

    plan.intent = (
        "diagnostics_"
        + mode
    )

    plan.confidence = (
        confidence
    )

    # Oude verkeerde specialistplanning mag nooit
    # door een herroutering blijven bestaan.
    plan.execution_steps = []

    # Alleen routegerelateerde entities vervangen.
    for key in (
        "diagnostics_mode",
        "diagnostics_domain",
        "diagnostics_depth",
    ):

        plan.entities.pop(
            key,
            None,
        )

    plan.entities[
        "diagnostics_mode"
    ] = _detected_entity(
        "diagnostics_mode",
        mode,
        confidence=confidence,
    )

    plan.entities[
        "diagnostics_domain"
    ] = _detected_entity(
        "diagnostics_domain",
        diagnostics_domain,
        confidence=confidence,
    )

    plan.entities[
        "diagnostics_depth"
    ] = _detected_entity(
        "diagnostics_depth",
        depth,
        confidence=confidence,
    )

    if not (
        plan.execution_blockers
        or []
    ):

        plan.clarification_required = (
            False
        )

        plan.clarification_question = (
            None
        )

    return plan


def apply_routing_sanity(
    plan: QueryPlan,
) -> QueryPlan:
    """
    Deterministische sanity-check na de eerste
    understanding/classification en vóór research.

    Geen specialist-call.
    Geen SQL.
    Geen HTTP.
    Geen write.

    P4.5b3 corrigeert uitsluitend:
    1. SYSTEM_META dat semantisch in een business/org-route
       terecht is gekomen;
    2. false-positive ORG als extra domein bij expliciete
       multi-productvragen zonder echte organisatie-intentie.

    Andere bestaande routes blijven ongemoeid.
    """

    # PROMATI_ROUTING_SANITY_LEGACY_PLAN_COMPAT_P4_5B3
    #
    # run_orchestrator heeft historisch ook tests/callers die
    # een minimale plan-compatible test double aanbieden.
    # Routing sanity is additief en mag die contracten niet
    # verplicht uitbreiden.
    #
    # Een echte QueryPlan uit understand_query bevat deze
    # velden altijd. Ontbreken ze, dan is er onvoldoende
    # routingcontext om veilig te corrigeren en blijft het
    # bestaande plan daarom ongewijzigd.
    required_routing_fields = (
        "query_class",
        "primary_domain",
        "domains",
        "intent",
    )

    if not all(
        hasattr(
            plan,
            field_name,
        )
        for field_name
        in required_routing_fields
    ):
        return plan

    query_class = (
        _enum_value(
            getattr(
                plan,
                "query_class",
                None,
            )
        )
    )

    primary_domain = (
        _enum_value(
            getattr(
                plan,
                "primary_domain",
                None,
            )
        )
    )

    intent = str(
        getattr(
            plan,
            "intent",
            "",
        )
        or ""
    ).strip().lower()

    # Pure system-meta wordt door understanding
    # bewust zonder specialist afgehandeld.
    if (
        query_class
        == "system_meta"
        and intent
        == "system_meta"
        and plan.primary_domain
        is None
    ):

        return plan

    # Een system/meta-vraag mag niet door succesvolle
    # evidence recovery als org_lookup worden gelegitimeerd.
    if (
        query_class
        == "system_meta"
        and (
            primary_domain
            != "diagnostics"
            or not intent.startswith(
                "diagnostics_"
            )
        )
    ):

        return (
            _repair_system_meta_route(
                plan
            )
        )

    family_codes = [
        str(
            getattr(
                item,
                "value",
                "",
            )
            or ""
        ).strip()
        for item
        in (
            getattr(
                plan,
                "product_families",
                None,
            )
            or []
        )
        if str(
            getattr(
                item,
                "value",
                "",
            )
            or ""
        ).strip()
    ]

    explicit_multi_product = (
        len(
            dict.fromkeys(
                family_codes
            )
        )
        >= 2
    )

    if (
        query_class
        == "business"
        and explicit_multi_product
        and not _has_explicit_org_intent(
            plan.normalized_question
            or plan.original_question
            or ""
        )
    ):

        had_org = (
            Domain.ORG
            in plan.domains
        )

        if had_org:

            plan.domains = [
                domain
                for domain
                in plan.domains
                if domain
                != Domain.ORG
            ]

            if (
                plan.primary_domain
                == Domain.ORG
            ):

                if (
                    Domain.PRODUCT
                    in plan.domains
                ):

                    plan.primary_domain = (
                        Domain.PRODUCT
                    )

                elif plan.domains:

                    plan.primary_domain = (
                        plan.domains[0]
                    )

                else:

                    plan.primary_domain = (
                        Domain.PRODUCT
                    )

                    plan.domains = [
                        Domain.PRODUCT,
                    ]

            if (
                str(
                    plan.intent
                    or ""
                ).lower()
                == "org_lookup"
            ):

                plan.intent = (
                    detect_intent(
                        plan.normalized_question,
                        plan.primary_domain,
                    )
                )

            # Oude planner-output nooit meenemen
            # na routecorrectie.
            plan.execution_steps = []

    return plan
