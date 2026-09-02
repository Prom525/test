from __future__ import annotations

from types import MappingProxyType

from app.orchestrator.evidence_contracts import (
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.evidence_requirements import (
    EVIDENCE_REQUIREMENT_CONTRACT_VERSION,
    EvidenceRequirement,
    EvidenceRequirementSet,
    RequirementNecessity,
)


def _requirement(
    requirement_id: str,
    evidence_types: tuple[EvidenceType, ...],
    necessity: RequirementNecessity,
    description: str,
    allowed_source_types: tuple[
        EvidenceSourceType,
        ...,
    ],
    *,
    minimum_items: int = 1,
    entity_type: str | None = None,
    entity_id_required: bool = False,
    maximum_age_seconds: float | None = None,
    forbidden_substitutions: tuple[
        EvidenceType,
        ...,
    ] = (),
) -> EvidenceRequirement:
    return EvidenceRequirement(
        contract_version=(
            EVIDENCE_REQUIREMENT_CONTRACT_VERSION
        ),
        requirement_id=requirement_id,
        evidence_types=evidence_types,
        necessity=necessity,
        description=description,
        allowed_source_types=allowed_source_types,
        minimum_items=minimum_items,
        entity_type=entity_type,
        entity_id_required=entity_id_required,
        maximum_age_seconds=maximum_age_seconds,
        forbidden_substitutions=(
            forbidden_substitutions
        ),
    )


def _requirement_set(
    intent: str,
    requirements: tuple[
        EvidenceRequirement,
        ...,
    ],
    *notes: str,
) -> EvidenceRequirementSet:
    return EvidenceRequirementSet(
        contract_version=(
            EVIDENCE_REQUIREMENT_CONTRACT_VERSION
        ),
        requirement_set_id=f"{intent}.v1",
        intent=intent,
        requirements=requirements,
        notes=tuple(notes),
    )



# PROMATI_INSPECTION_LATEST_REQUIREMENTS_V1
_INSPECTION_LATEST = _requirement_set(
    "inspection_latest",
    (
        _requirement(
            "RESOLVED_ASSET_CONTEXT",
            (EvidenceType.ASSET_RESOLUTION,),
            RequirementNecessity.REQUIRED,
            "Resolved canonical conveyor-belt context.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_INSPECTION_DATE",
            (EvidenceType.EVENT,),
            RequirementNecessity.REQUIRED,
            "Observation date of the latest known inspection.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="inspection",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_INSPECTION_MEASUREMENT",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Latest known blade-height observation per scraper position.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
    ),
    (
        "Latest-known semantics: this requirement set proves the newest "
        "known canonical inspection, not calendar recency.",
        "Inspection check details and comments are intentionally outside "
        "this V1 requirement set because they are multi-record detail data.",
    ),
)


_BAND_STATUS = _requirement_set(
    "band_status",
    (
        _requirement(
            "CURRENT_SCRAPER_CONFIGURATION",
            (
                EvidenceType.RECORD,
                EvidenceType.STATUS,
            ),
            RequirementNecessity.REQUIRED,
            "Current scraper configuration.",
            (
                EvidenceSourceType.LIVE_CANONICAL,
                EvidenceSourceType.SPECIALIST_RESULT,
            ),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_BLADE_HEIGHT",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Latest observed blade height.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "MEASUREMENT_DATE",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Observation time of the latest measurement.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "LIFECYCLE_TREND",
            (
                EvidenceType.MEASUREMENT,
                EvidenceType.EVENT,
            ),
            RequirementNecessity.DESIRED,
            "Observed lifecycle history.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=2,
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
    ),
)

_SCRAPER_STATUS = _requirement_set(
    "scraper_status",
    (
        _requirement(
            "CURRENT_SCRAPER_CONFIGURATION",
            (
                EvidenceType.RECORD,
                EvidenceType.STATUS,
            ),
            RequirementNecessity.REQUIRED,
            "Current scraper configuration.",
            (
                EvidenceSourceType.LIVE_CANONICAL,
                EvidenceSourceType.SPECIALIST_RESULT,
            ),
            entity_type="scraper",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_BLADE_HEIGHT",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Latest blade-height observation.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper",
            entity_id_required=True,
        ),
        _requirement(
            "MAINTENANCE_STATUS",
            (EvidenceType.STATUS,),
            RequirementNecessity.DESIRED,
            "Observed maintenance status.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper",
            entity_id_required=True,
        ),
    ),
)

# PROMATI_INSPECTION_TREND_REQUIREMENTS_V1
_INSPECTION_TREND = _requirement_set(
    "inspection_trend",
    (
        _requirement(
            "RESOLVED_ASSET_CONTEXT",
            (EvidenceType.ASSET_RESOLUTION,),
            RequirementNecessity.REQUIRED,
            "Resolved canonical conveyor-belt context.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "MEASUREMENT_HISTORY",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Chronological observed blade-height measurements.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=2,
            entity_type="scraper_position",
            entity_id_required=True,
        ),
        _requirement(
            "REPLACEMENT_HISTORY",
            (EvidenceType.EVENT,),
            RequirementNecessity.REQUIRED_FOR_DIAGNOSIS,
            "Observed scraper replacement events.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
        _requirement(
            "INSPECTION_COMMENTS",
            (EvidenceType.RECORD,),
            RequirementNecessity.DESIRED,
            "Recorded lifecycle inspection comments.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
    ),
    (
        "Trend semantics require at least two usable observations.",
        "Forecast reliability is intentionally outside this V1 set; "
        "a reliable forecast requires at least three usable points.",
        "Historical observations use NOT_APPLICABLE freshness.",
    ),
)


_LIFECYCLE_ANALYSIS = _requirement_set(
    "lifecycle_analysis",
    (
        _requirement(
            "MEASUREMENT_HISTORY",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Chronological observed measurements.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=2,
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "REPLACEMENT_HISTORY",
            (EvidenceType.EVENT,),
            RequirementNecessity.REQUIRED_FOR_DIAGNOSIS,
            "Observed replacement events.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "INSPECTION_COMMENTS",
            (EvidenceType.RECORD,),
            RequirementNecessity.DESIRED,
            "Recorded inspection comments.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
    ),
)

# PROMATI_MAINTENANCE_PRIORITY_REQUIREMENTS_V1
_MAINTENANCE_PRIORITY = _requirement_set(
    "maintenance_priority",
    (
        _requirement(
            "RESOLVED_ASSET_CONTEXT",
            (EvidenceType.ASSET_RESOLUTION,),
            RequirementNecessity.REQUIRED,
            "Resolved canonical conveyor-belt context.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "MAINTENANCE_POSITION_STATUS",
            (EvidenceType.STATUS,),
            RequirementNecessity.REQUIRED,
            "Derived maintenance status per analysed scraper position.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=1,
            entity_type="maintenance_position",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_POSITION_MEASUREMENT",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED_FOR_DIAGNOSIS,
            "Latest directly observed blade height for an analysed position.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=1,
            entity_type="maintenance_position",
            entity_id_required=True,
        ),
        _requirement(
            "FORECAST_RESULT",
            (EvidenceType.CALCULATION_RESULT,),
            RequirementNecessity.DESIRED,
            "Derived replacement-threshold forecast where sufficient usable measurements exist.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=1,
            entity_type="maintenance_position",
            entity_id_required=True,
        ),
    ),
    (
        "Maintenance status and forecast are derived evidence.",
        "Latest observed blade height remains direct measurement evidence.",
        "Forecast evidence is emitted only with at least three usable points and complete calculation fields.",
        "The hard replacement threshold remains 3 mm.",
    ),
)


# PROMATI_REPLACEMENT_ADVICE_REQUIREMENTS_V1
_REPLACEMENT_ADVICE = _requirement_set(
    "replacement_advice",
    (
        _requirement(
            "RESOLVED_ASSET_CONTEXT",
            (EvidenceType.ASSET_RESOLUTION,),
            RequirementNecessity.REQUIRED,
            "Resolved canonical conveyor-belt context.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="conveyor_belt",
            entity_id_required=True,
        ),
        _requirement(
            "LATEST_POSITION_MEASUREMENT",
            (EvidenceType.MEASUREMENT,),
            RequirementNecessity.REQUIRED,
            "Latest observed blade height per scraper position.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
        _requirement(
            "LIFECYCLE_HISTORY",
            (
                EvidenceType.MEASUREMENT,
                EvidenceType.EVENT,
            ),
            RequirementNecessity.REQUIRED_FOR_DIAGNOSIS,
            "Observed lifecycle development per scraper position.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            minimum_items=2,
            entity_type="scraper_lifecycle",
            entity_id_required=True,
        ),
        _requirement(
            "REPLACEMENT_HISTORY",
            (EvidenceType.EVENT,),
            RequirementNecessity.DESIRED,
            "Observed executed replacement events.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_lifecycle",
            entity_id_required=True,
        ),
        _requirement(
            "FORECAST_RESULT",
            (EvidenceType.CALCULATION_RESULT,),
            RequirementNecessity.DESIRED,
            (
                "Derived 3 mm replacement-threshold forecast "
                "where sufficient usable measurements exist."
            ),
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
        _requirement(
            "DIAGNOSTIC_FINDING",
            (EvidenceType.DIAGNOSTIC_FINDING,),
            RequirementNecessity.DESIRED,
            "Derived replacement-advice diagnostic finding.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="scraper_position",
            entity_id_required=True,
        ),
    ),
    (
        "The hard replacement threshold remains 3 mm."
    ),
    (
        "A derived maintenance recommendation such as "
        "VERVANGEN_VOORBEREIDEN is not an executed "
        "replacement and is not equivalent to NU VERVANGEN."
    ),
    (
        "Forecast evidence requires at least three usable "
        "measurements and complete calculation fields."
    ),
)

_PRODUCT_LOOKUP = _requirement_set(
    "product_lookup",
    (
        _requirement(
            "PRODUCT_RECORD",
            (EvidenceType.RECORD,),
            RequirementNecessity.REQUIRED,
            "Matching controlled product record.",
            (
                EvidenceSourceType.STRUCTURED_KNOWLEDGE,
            ),
            entity_type="product",
        ),
    ),
)

_PRICE_STOCK = _requirement_set(
    "price_stock",
    (
        _requirement(
            "CURRENT_PRICE",
            (EvidenceType.RECORD,),
            RequirementNecessity.REQUIRED,
            "Current canonical price record.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="product",
            entity_id_required=True,
            forbidden_substitutions=(
                EvidenceType.DOCUMENT_FRAGMENT,
            ),
        ),
        _requirement(
            "CURRENT_STOCK",
            (EvidenceType.STATUS,),
            RequirementNecessity.REQUIRED,
            "Current canonical stock status.",
            (EvidenceSourceType.LIVE_CANONICAL,),
            entity_type="product",
            entity_id_required=True,
            forbidden_substitutions=(
                EvidenceType.DOCUMENT_FRAGMENT,
            ),
        ),
    ),
    "Historical documents do not substitute live price or stock.",
)

_TECHNICAL_LOOKUP = _requirement_set(
    "technical_lookup",
    (
        _requirement(
            "TECHNICAL_SOURCE",
            (
                EvidenceType.DOCUMENT_FRAGMENT,
                EvidenceType.RECORD,
            ),
            RequirementNecessity.REQUIRED,
            "Controlled technical source content.",
            (
                EvidenceSourceType.STRUCTURED_KNOWLEDGE,
                EvidenceSourceType.APPROVED_DOCUMENT,
                EvidenceSourceType.RAG_CONTEXT,
            ),
        ),
    ),
)

_TECHNICAL_CALCULATION = _requirement_set(
    "technical_calculation",
    (
        _requirement(
            "CALCULATION_INPUTS",
            (EvidenceType.RECORD,),
            RequirementNecessity.REQUIRED,
            "Explicit calculation inputs.",
            (
                EvidenceSourceType.STRUCTURED_KNOWLEDGE,
                EvidenceSourceType.LIVE_CANONICAL,
            ),
        ),
        _requirement(
            "CALCULATION_RESULT",
            (EvidenceType.CALCULATION_RESULT,),
            RequirementNecessity.REQUIRED,
            "Deterministic calculation result.",
            (EvidenceSourceType.CALCULATION,),
        ),
    ),
)

_PERSON_ROLE_LOOKUP = _requirement_set(
    "person_role_lookup",
    (
        _requirement(
            "CURRENT_PERSON_ROLE",
            (EvidenceType.RECORD,),
            RequirementNecessity.REQUIRED,
            "Current person-to-role record.",
            (EvidenceSourceType.SPECIALIST_RESULT,),
            entity_type="person_role",
            entity_id_required=True,
            forbidden_substitutions=(
                EvidenceType.DOCUMENT_FRAGMENT,
            ),
        ),
    ),
)

_RFQ_STATUS = _requirement_set(
    "rfq_status",
    (
        _requirement(
            "RFQ_STATUS",
            (EvidenceType.STATUS,),
            RequirementNecessity.REQUIRED,
            "Canonical RFQ status record.",
            (
                EvidenceSourceType.LIVE_CANONICAL,
                EvidenceSourceType.SPECIALIST_RESULT,
            ),
            entity_type="rfq",
            entity_id_required=True,
            forbidden_substitutions=(
                EvidenceType.DOCUMENT_FRAGMENT,
            ),
        ),
    ),
)

_DIAGNOSTICS_HEALTH = _requirement_set(
    "diagnostics_health",
    (
        _requirement(
            "DIAGNOSTIC_FINDING",
            (EvidenceType.DIAGNOSTIC_FINDING,),
            RequirementNecessity.REQUIRED,
            "Explicit diagnostic finding.",
            (EvidenceSourceType.DIAGNOSTIC,),
        ),
        _requirement(
            "DIAGNOSTIC_SCOPE",
            (EvidenceType.RECORD,),
            RequirementNecessity.DESIRED,
            "Scope and source-table metadata.",
            (EvidenceSourceType.DIAGNOSTIC,),
        ),
    ),
)


REQUIREMENT_SETS_BY_INTENT = MappingProxyType(
    {
        item.intent: item
        for item in (
            _INSPECTION_LATEST,
            _INSPECTION_TREND,
            _BAND_STATUS,
            _SCRAPER_STATUS,
            _LIFECYCLE_ANALYSIS,
            _MAINTENANCE_PRIORITY,
            _REPLACEMENT_ADVICE,
            _PRODUCT_LOOKUP,
            _PRICE_STOCK,
            _TECHNICAL_LOOKUP,
            _TECHNICAL_CALCULATION,
            _PERSON_ROLE_LOOKUP,
            _RFQ_STATUS,
            _DIAGNOSTICS_HEALTH,
        )
    }
)


INTENT_REQUIREMENT_ALIASES = MappingProxyType(
    {
        "org_lookup": "person_role_lookup",

        # PROMATI_MULTI_PRODUCT_REQUIREMENT_ALIASES_P4_5B4
        # Product comparison/advantages still require the same
        # controlled PRODUCT_RECORD evidence as product_lookup.
        "product_selection": "product_lookup",
        "advantages_disadvantages": "product_lookup",
    }
)


def get_requirement_set(
    intent: str,
) -> EvidenceRequirementSet | None:
    resolved_intent = INTENT_REQUIREMENT_ALIASES.get(
        intent,
        intent,
    )

    return REQUIREMENT_SETS_BY_INTENT.get(
        resolved_intent
    )


__all__ = [
    "REQUIREMENT_SETS_BY_INTENT",
    "get_requirement_set",
]
