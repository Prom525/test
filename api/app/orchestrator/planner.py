from app.orchestrator.models import (
    Domain,
    ExecutionStep,
    QueryPlan,
)


def _entity_value(
    plan: QueryPlan,
    name: str,
):
    entity = plan.entities.get(name)
    return entity.value if entity else None


def _ordered_domains(
    plan: QueryPlan,
) -> list[Domain]:
    """
    Primary domain eerst, daarna eventuele aanvullende domeinen.
    Duplicaten worden verwijderd met behoud van volgorde.

    Diagnostics is exclusief wanneer dit het primaire domein is:
    de diagnostics-service kan zelf inspection/database/system
    context onderzoeken.
    """

    if plan.primary_domain == Domain.DIAGNOSTICS:
        return [Domain.DIAGNOSTICS]

    ordered: list[Domain] = []

    if plan.primary_domain is not None:
        ordered.append(plan.primary_domain)

    for domain in plan.domains:
        if domain not in ordered:
            ordered.append(domain)

    return ordered



def _build_product_step(
    plan: QueryPlan,
    step_no: int,
    *,
    family_code: str | None = None,
    multi_family: bool = False,
) -> ExecutionStep:
    params = {
        "vraag": plan.original_question,
        "mode": "auto",
    }

    resolved_family_code = (
        family_code
        if family_code is not None
        else _entity_value(
            plan,
            "family_code",
        )
    )

    belt_width_mm = _entity_value(
        plan,
        "belt_width_mm",
    )

    if resolved_family_code is not None:
        params["family_code"] = (
            resolved_family_code
        )

    if belt_width_mm is not None:
        params["belt_width_mm"] = (
            belt_width_mm
        )

    if (
        multi_family
        and resolved_family_code is not None
    ):
        step_id = (
            f"step_{step_no}_product_"
            f"{resolved_family_code}"
        )
    else:
        step_id = (
            f"step_{step_no}_product"
        )

    return ExecutionStep(
        step_id=step_id,
        domain=Domain.PRODUCT,
        action="product_assistant",
        params=params,
        required=True,
        fallback_allowed=True,
    )



def _build_inspection_step(
    plan: QueryPlan,
    step_no: int,
) -> ExecutionStep:
    lijn_code = _entity_value(
        plan,
        "lijn_code",
    )

    band_code = _entity_value(
        plan,
        "band_code",
    )

    scraper_type = _entity_value(
        plan,
        "scraper_type",
    )

    # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
    scraper_family = _entity_value(
        plan,
        "scraper_family",
    )

    # PROMATI_SCOPE_CONTRACT_PLANNER_V13_1
    scope_code = _entity_value(
        plan,
        "scope_code",
    )
    scope_type = _entity_value(
        plan,
        "scope_type",
    )
    area_code = _entity_value(
        plan,
        "area_code",
    )
    installation_code = _entity_value(
        plan,
        "installation_code",
    )

    execution_question = plan.original_question

    # analysis_api_v10 heeft geen expliciet intent/mode-contract.
    # Wanneer de orchestrator de intent al betrouwbaar heeft bepaald
    # en een bandcode bekend is, sturen we daarom een canonieke
    # uitvoeringsvraag die de bestaande analysis-intentdetector
    # ondubbelzinnig kan routeren.
    #
    # De originele gebruikersvraag blijft ongewijzigd bewaard in
    # QueryPlan.original_question.
    if band_code is not None:
        canonical_questions = {
            "inspection_latest": (
                f"laatste inspecties van band {band_code}"
            ),
            "inspection_lookup": (
                f"inspectieoverzicht van band {band_code}"
            ),
            "inspection_trend": (
                f"toon de trend van band {band_code}"
            ),
            "maintenance_priority": (
                f"onderhoudsplanning voor band {band_code}"
            ),
            # PROMATI_REPLACEMENT_ADVICE_PLANNER_V1
            "replacement_advice": (
                f"vervangadvies voor band {band_code}"
            ),
        }

        execution_question = canonical_questions.get(
            plan.intent,
            execution_question,
        )

    params = {
        "vraag": execution_question,
        "mode": "auto",
    }

    if lijn_code is not None:
        params["lijn_code"] = lijn_code

    if band_code is not None:
        params["band_code"] = band_code

    if scraper_type is not None:
        params["scraper_type"] = scraper_type

    # PROMATI_SCOPE_SCRAPER_FAMILY_FILTER_V1
    if scraper_family is not None:
        params["scraper_family"] = scraper_family

    if scope_code is not None:
        params["scope_code"] = scope_code

    if scope_type is not None:
        params["scope_type"] = scope_type

    if area_code is not None:
        params["area_code"] = area_code

    if installation_code is not None:
        params["installation_code"] = (
            installation_code
        )

    return ExecutionStep(
        step_id=f"step_{step_no}_inspection",
        domain=Domain.INSPECTION,
        action="analysis_assistant",
        params=params,
        required=True,
        fallback_allowed=True,
    )


def _build_technical_step(
    plan: QueryPlan,
    step_no: int,
) -> ExecutionStep:
    return ExecutionStep(
        step_id=f"step_{step_no}_technical",
        domain=Domain.TECHNICAL,
        action="technical_assistant",
        params={
            "vraag": plan.original_question,
            "use_rag": True,
        },
        required=True,
        fallback_allowed=True,
    )


def _build_org_step(
    plan: QueryPlan,
    step_no: int,
) -> ExecutionStep:
    return ExecutionStep(
        step_id=f"step_{step_no}_org",
        domain=Domain.ORG,
        action="org_assistant",
        params={
            "vraag": plan.original_question,
            "firma": "Promati",
            "mode": "auto",
        },
        required=True,
        fallback_allowed=True,
    )



# PROMATI_DIAGNOSTICS_PLANNER_V1
def _build_diagnostics_step(
    plan: QueryPlan,
    step_no: int,
) -> ExecutionStep:
    mode = (
        _entity_value(
            plan,
            "diagnostics_mode",
        )
        or "overview"
    )

    diagnostics_domain = (
        _entity_value(
            plan,
            "diagnostics_domain",
        )
        or "database"
    )

    depth = (
        _entity_value(
            plan,
            "diagnostics_depth",
        )
        or "normal"
    )

    objects = _entity_value(
        plan,
        "diagnostics_objects",
    )

    lijn_code = _entity_value(
        plan,
        "lijn_code",
    )

    band_code = _entity_value(
        plan,
        "band_code",
    )

    params = {
        "vraag": plan.original_question,
        "domain": str(diagnostics_domain),
        "mode": str(mode),
        "depth": str(depth),
        "limit": 50,
    }

    if isinstance(objects, list) and objects:
        params["objects"] = objects

    if lijn_code is not None:
        params["lijn_code"] = lijn_code

    if band_code is not None:
        params["band_code"] = band_code

    return ExecutionStep(
        step_id=f"step_{step_no}_diagnostics",
        domain=Domain.DIAGNOSTICS,
        action="diagnostics_assistant",
        params=params,
        required=True,
        fallback_allowed=True,
    )



# PROMATI_MULTI_PRODUCT_PLANNER_FANOUT_P4_5B2
def build_execution_plan(
    plan: QueryPlan,
) -> QueryPlan:
    """
    Bouwt alleen execution_steps.

    Geen HTTP-calls.
    Geen database-acties.
    Geen fallback-uitvoering.

    Multi-productvragen worden per expliciet genoemde
    productfamilie uitgewaaierd naar dezelfde allowlisted
    product_assistant.

    Als clarification nodig is, wordt bewust niets uitgevoerd.
    """

    plan.execution_steps = []

    # PROMATI_PHASE_A2D_EXECUTION_GROUNDING_V1
    # Execution safety is independent from clarification UX.
    if plan.execution_blockers:
        return plan

    if plan.clarification_required:
        return plan

    domains = _ordered_domains(
        plan
    )

    next_step_no = 1

    for domain in domains:

        if domain == Domain.PRODUCT:
            family_codes = [
                str(item.value).strip()
                for item in (
                    plan.product_families
                    or []
                )
                if item.value is not None
                and str(item.value).strip()
            ]

            # Alleen echte multi-family vragen fan-out.
            if len(family_codes) > 1:
                for family_code in family_codes:
                    plan.execution_steps.append(
                        _build_product_step(
                            plan,
                            next_step_no,
                            family_code=family_code,
                            multi_family=True,
                        )
                    )

                    next_step_no += 1

            else:
                plan.execution_steps.append(
                    _build_product_step(
                        plan,
                        next_step_no,
                    )
                )

                next_step_no += 1

        elif domain == Domain.INSPECTION:
            plan.execution_steps.append(
                _build_inspection_step(
                    plan,
                    next_step_no,
                )
            )

            next_step_no += 1

        elif domain == Domain.TECHNICAL:
            plan.execution_steps.append(
                _build_technical_step(
                    plan,
                    next_step_no,
                )
            )

            next_step_no += 1

        elif domain == Domain.ORG:
            plan.execution_steps.append(
                _build_org_step(
                    plan,
                    next_step_no,
                )
            )

            next_step_no += 1

        elif domain == Domain.DIAGNOSTICS:
            plan.execution_steps.append(
                _build_diagnostics_step(
                    plan,
                    next_step_no,
                )
            )

            next_step_no += 1

    return plan
