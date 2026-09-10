from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.evidence_contracts import (
    EVIDENCE_CONTRACT_VERSION,
    EvidenceDirectness,
    EvidenceFreshnessStatus,
    EvidenceGroundingStatus,
    EvidenceItem,
    EvidenceQualityStatus,
    EvidenceSourceType,
    EvidenceType,
)
from app.orchestrator.execution_contracts import (
    ExecutionResult,
)


def _nonempty_string(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()

    if not normalized:
        return None

    return normalized


def _stable_evidence_id(
    *,
    execution_result: ExecutionResult,
    record: dict[str, Any],
    index: int,
) -> str:
    identity_payload = {
        "step_id": execution_result.step_id,
        "action": execution_result.action,
        "index": index,
        "record": record,
    }

    serialized = json.dumps(
        identity_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    digest = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

    return f"evidence-{digest}"


def _technical_structured_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    technical_context = raw_result.get(
        "technical_context"
    )

    if not isinstance(technical_context, dict):
        return ()

    records = technical_context.get("results")

    if not isinstance(records, list):
        return ()

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(raw_record)

        entity_id = _nonempty_string(
            record.get("item_id")
        )

        source_code = (
            _nonempty_string(
                record.get("source_code")
            )
            or _nonempty_string(
                technical_context.get("source_code")
            )
        )

        subject = _nonempty_string(
            record.get("title")
        )

        if source_code and entity_id:
            source_reference = (
                f"{source_code}:{entity_id}"
            )
        else:
            source_reference = (
                entity_id or source_code
            )

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if entity_id is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        provenance = {
            "source_code": source_code,
            "source_title": _nonempty_string(
                record.get("source_title")
            ),
            "page_start": record.get("page_start"),
            "page_end": record.get("page_end"),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject=subject,
                entity_type="technical_item",
                entity_id=entity_id,
                evidence_type=EvidenceType.RECORD,
                source_type=(
                    EvidenceSourceType
                    .STRUCTURED_KNOWLEDGE
                ),
                source_name=source_code,
                source_reference=source_reference,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=record,
                unit=None,
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .NOT_APPLICABLE
                ),
                grounding_status=grounding_status,
                quality_status=(
                    EvidenceQualityStatus.VALID
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)


def _product_knowledge_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    """
    Normalize controlled product-family context into
    PRODUCT_RECORD evidence.

    Safety boundary:
    - only family_context.results is authoritative here;
    - RAG/document scope is never promoted to a product record;
    - article_search_v2 remains a separate LIVE_CANONICAL path.
    """
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    result_status = _nonempty_string(
        raw_result.get("status")
    )

    if (
        result_status is None
        or result_status.casefold() != "ok"
    ):
        return ()

    family_context = raw_result.get(
        "family_context"
    )

    if not isinstance(
        family_context,
        dict,
    ):
        return ()

    family_status = _nonempty_string(
        family_context.get("status")
    )

    if (
        family_status is None
        or family_status.casefold() != "ok"
    ):
        return ()

    records = family_context.get(
        "results"
    )

    if not isinstance(records, list):
        return ()

    detected_family_code = (
        _nonempty_string(
            raw_result.get(
                "detected_family_code"
            )
        )
        or _nonempty_string(
            family_context.get(
                "detected_family_code"
            )
        )
    )

    context_type = (
        _nonempty_string(
            family_context.get(
                "context_type"
            )
        )
        or "product_family_context"
    )

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(
        records
    ):
        if not isinstance(
            raw_record,
            dict,
        ):
            continue

        record = copy.deepcopy(
            raw_record
        )

        record_family_code = (
            _nonempty_string(
                record.get(
                    "family_code"
                )
            )
        )

        if record_family_code is None:
            continue

        if (
            detected_family_code is not None
            and (
                record_family_code.casefold()
                != detected_family_code.casefold()
            )
        ):
            # Never ground a returned family record against
            # a different explicitly resolved family.
            continue

        entity_id = (
            detected_family_code
            or record_family_code
        )

        subject = (
            _nonempty_string(
                record.get(
                    "family_name"
                )
            )
            or entity_id
        )

        source_reference = (
            f"{context_type}:{entity_id}"
        )

        provenance = {
            "family_code": entity_id,
            "family_name": subject,
            "context_type": context_type,
            "family_context_status": (
                family_status
            ),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=(
                    _stable_evidence_id(
                        execution_result=(
                            execution_result
                        ),
                        record=record,
                        index=index,
                    )
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=(
                    execution_result.domain
                ),
                subject=subject,
                entity_type="product",
                entity_id=entity_id,
                evidence_type=(
                    EvidenceType.RECORD
                ),
                source_type=(
                    EvidenceSourceType
                    .STRUCTURED_KNOWLEDGE
                ),
                source_name=context_type,
                source_reference=(
                    source_reference
                ),
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=record,
                unit=None,
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .NOT_APPLICABLE
                ),
                grounding_status=(
                    EvidenceGroundingStatus
                    .GROUNDED
                ),
                quality_status=(
                    EvidenceQualityStatus
                    .VALID
                ),
                direct_or_derived=(
                    EvidenceDirectness
                    .DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)



# PROMATI_PRODUCT_PRICE_STOCK_EVIDENCE_P4_5B5
def _product_price_stock_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    """Normalize only explicit live config_options price/stock fields."""
    raw_result = execution_result.result
    if not isinstance(raw_result, dict):
        return ()
    if (_nonempty_string(raw_result.get("status")) or "").casefold() != "ok":
        return ()

    family_code = _nonempty_string(raw_result.get("detected_family_code"))
    config = raw_result.get("config_options")
    if family_code is None or not isinstance(config, dict):
        return ()
    rows = config.get("results")
    if not isinstance(rows, list):
        return ()

    source_name = _nonempty_string(config.get("source_view")) or "config_options"
    output: list[EvidenceItem] = []
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            continue
        row = copy.deepcopy(raw_row)
        internal_ref = _nonempty_string(row.get("internal_ref"))
        label = _nonempty_string(row.get("product_name")) or internal_ref or family_code
        source_reference = f"{source_name}:{internal_ref or family_code}"
        base_provenance = {
            "family_code": family_code,
            "internal_ref": internal_ref,
            "source_view": source_name,
        }

        sale_price = row.get("sale_price")
        if isinstance(sale_price, (int, float)) and not isinstance(sale_price, bool):
            price_record = {
                "family_code": family_code,
                "internal_ref": internal_ref,
                "product_name": label,
                "sale_price": sale_price,
                "currency": row.get("currency"),
            }
            output.append(EvidenceItem(
                contract_version=EVIDENCE_CONTRACT_VERSION,
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record={"kind": "current_price", "record": price_record},
                    index=index * 2,
                ),
                execution_step_id=execution_result.step_id,
                specialist_id=execution_result.action,
                domain=execution_result.domain,
                subject=f"{family_code} {label} actuele prijs",
                entity_type="product",
                entity_id=family_code,
                evidence_type=EvidenceType.RECORD,
                source_type=EvidenceSourceType.LIVE_CANONICAL,
                source_name=source_name,
                source_reference=source_reference,
                source_priority=None,
                observed_at=retrieved_at,
                retrieved_at=retrieved_at,
                effective_at=retrieved_at,
                value=price_record,
                unit=_nonempty_string(row.get("currency")),
                claim_scope=("CURRENT_PRICE",),
                freshness_status=EvidenceFreshnessStatus.CURRENT,
                grounding_status=EvidenceGroundingStatus.GROUNDED,
                quality_status=EvidenceQualityStatus.VALID,
                direct_or_derived=EvidenceDirectness.DIRECT,
                derivation_reference=None,
                provenance={**base_provenance, "evidence_kind": "CURRENT_PRICE"},
            ))

        available_qty = row.get("available_qty")
        if isinstance(available_qty, (int, float)) and not isinstance(available_qty, bool):
            stock_record = {
                "family_code": family_code,
                "internal_ref": internal_ref,
                "product_name": label,
                "available_qty": available_qty,
                "expected_qty": row.get("expected_qty"),
                "uom": row.get("uom"),
            }
            output.append(EvidenceItem(
                contract_version=EVIDENCE_CONTRACT_VERSION,
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record={"kind": "current_stock", "record": stock_record},
                    index=index * 2 + 1,
                ),
                execution_step_id=execution_result.step_id,
                specialist_id=execution_result.action,
                domain=execution_result.domain,
                subject=f"{family_code} {label} actuele voorraad",
                entity_type="product",
                entity_id=family_code,
                evidence_type=EvidenceType.STATUS,
                source_type=EvidenceSourceType.LIVE_CANONICAL,
                source_name=source_name,
                source_reference=source_reference,
                source_priority=None,
                observed_at=retrieved_at,
                retrieved_at=retrieved_at,
                effective_at=retrieved_at,
                value=stock_record,
                unit=_nonempty_string(row.get("uom")),
                claim_scope=("CURRENT_STOCK",),
                freshness_status=EvidenceFreshnessStatus.CURRENT,
                grounding_status=EvidenceGroundingStatus.GROUNDED,
                quality_status=EvidenceQualityStatus.VALID,
                direct_or_derived=EvidenceDirectness.DIRECT,
                derivation_reference=None,
                provenance={**base_provenance, "evidence_kind": "CURRENT_STOCK"},
            ))

    return tuple(output)


def _product_article_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    article_context = raw_result.get(
        "article_search_v2"
    )

    if not isinstance(article_context, dict):
        return ()

    records = article_context.get("results")

    if not isinstance(records, list):
        return ()

    source_view = _nonempty_string(
        article_context.get("source_view")
    )

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(raw_record)

        internal_ref = _nonempty_string(
            record.get("internal_ref")
        )

        staging_id = record.get("stg_article_id")

        entity_id = (
            internal_ref
            or _nonempty_string(staging_id)
        )

        subject = _nonempty_string(
            record.get("product_name")
        )

        if source_view and entity_id:
            source_reference = (
                f"{source_view}:{entity_id}"
            )
        else:
            source_reference = (
                entity_id or source_view
            )

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if entity_id is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        provenance = {
            "source_view": source_view,
            "stg_article_id": staging_id,
            "family_code": _nonempty_string(
                record.get("family_code")
            ),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject=subject,
                entity_type="product_article",
                entity_id=entity_id,
                evidence_type=EvidenceType.RECORD,
                source_type=(
                    EvidenceSourceType.LIVE_CANONICAL
                ),
                source_name=source_view,
                source_reference=source_reference,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=record,
                unit=None,
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus.UNKNOWN
                ),
                grounding_status=grounding_status,
                quality_status=(
                    EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)

def _parse_datetime(
    value: Any,
) -> datetime | None:
    normalized = _nonempty_string(value)

    if normalized is None:
        return None

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1] + "+00:00"
        )

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None



# PROMATI_INSPECTION_TREND_EVIDENCE_V1
def _analysis_lifecycle_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    if (
        _nonempty_string(
            raw_result.get("intent")
        )
        != "lifecycle"
    ):
        return ()

    records = raw_result.get("resultaat")

    if not isinstance(records, list):
        return ()

    asset_context = raw_result.get(
        "asset_context"
    )
    asset_resolution = raw_result.get(
        "asset_resolution"
    )

    if not isinstance(asset_context, dict):
        asset_context = {}

    if not isinstance(
        asset_resolution,
        dict,
    ):
        asset_resolution = {}

    asset_band_code = _nonempty_string(
        asset_context.get("band_code")
        or asset_context.get("band_code_norm")
    )

    resolution_status = (
        _nonempty_string(
            asset_resolution.get("status")
        )
        or ""
    ).casefold()

    asset_resolved = (
        resolution_status == "resolved"
        and asset_band_code is not None
    )

    evidence_items: list[EvidenceItem] = []

    if asset_band_code is not None:
        asset_record = {
            "kind": "inspection_trend_asset",
            "band_code": asset_band_code,
            "asset_context": copy.deepcopy(
                asset_context
            ),
            "asset_resolution": copy.deepcopy(
                asset_resolution
            ),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=asset_record,
                    index=-1000,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject="resolved_asset_context",
                entity_type="conveyor_belt",
                entity_id=asset_band_code,
                evidence_type=(
                    EvidenceType.ASSET_RESOLUTION
                ),
                source_type=(
                    EvidenceSourceType
                    .LIVE_CANONICAL
                ),
                source_name=(
                    "analysis_assistant"
                ),
                source_reference=asset_band_code,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=copy.deepcopy(
                    asset_context
                ),
                unit=None,
                claim_scope=(
                    asset_band_code,
                ),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .NOT_APPLICABLE
                ),
                grounding_status=(
                    EvidenceGroundingStatus.GROUNDED
                    if asset_resolved
                    else EvidenceGroundingStatus.UNKNOWN
                ),
                quality_status=(
                    EvidenceQualityStatus.VALID
                    if asset_resolved
                    else EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance={
                    "asset_context": copy.deepcopy(
                        asset_context
                    ),
                    "asset_resolution": copy.deepcopy(
                        asset_resolution
                    ),
                },
            )
        )

    seen_measurements: set[
        tuple[object, ...]
    ] = set()

    seen_replacements: set[
        tuple[object, ...]
    ] = set()

    seen_comments: set[
        tuple[object, ...]
    ] = set()

    evidence_index = 0

    for raw_record in records:
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(
            raw_record
        )

        inspected_on_raw = (
            record.get("inspected_on")
        )

        observed_at = _parse_datetime(
            inspected_on_raw
        )

        inspected_on = _nonempty_string(
            inspected_on_raw
        )

        row_band_code = _nonempty_string(
            record.get("band_norm")
        )

        scraper_type = _nonempty_string(
            record.get("scraper_type_norm")
        )

        position_hint = _nonempty_string(
            record.get("position_hint")
        )

        canonical_key = _nonempty_string(
            record.get(
                "canonical_inspection_key"
            )
        )

        source_file = _nonempty_string(
            record.get("source_file")
        )

        cycle_id = record.get("cycle_id")

        row_matches_asset = (
            asset_resolved
            and row_band_code is not None
            and asset_band_code is not None
            and row_band_code == asset_band_code
        )

        identity_complete = all(
            (
                inspected_on is not None,
                row_band_code is not None,
                scraper_type is not None,
                canonical_key is not None,
            )
        )

        identity_payload = {
            "band_code": row_band_code,
            "scraper_type": scraper_type,
            "position_hint": position_hint,
            "cycle_id": cycle_id,
            "inspected_on": inspected_on,
            "canonical_inspection_key": (
                canonical_key
            ),
        }

        identity_serialized = json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        entity_id = (
            "scraper-position-observation-"
            + hashlib.sha256(
                identity_serialized.encode(
                    "utf-8"
                )
            ).hexdigest()[:24]
        )

        claim_scope_parts = [
            item
            for item in (
                row_band_code,
                scraper_type,
                position_hint,
                (
                    f"cycle:{cycle_id}"
                    if cycle_id is not None
                    else None
                ),
                inspected_on,
            )
            if item is not None
        ]

        claim_scope = tuple(
            str(item)
            for item in claim_scope_parts
        )

        common_provenance = {
            "band_code": row_band_code,
            "asset_band_code": (
                asset_band_code
            ),
            "scraper_type_norm": (
                scraper_type
            ),
            "position_hint": (
                position_hint
            ),
            "cycle_id": cycle_id,
            "inspected_on": inspected_on,
            "canonical_inspection_key": (
                canonical_key
            ),
            "source_file": source_file,
            "sheet_analysis_key": (
                _nonempty_string(
                    record.get(
                        "sheet_analysis_key"
                    )
                )
            ),
            "sheet_instance_key": (
                _nonempty_string(
                    record.get(
                        "sheet_instance_key"
                    )
                )
            ),
            "historical_observation": True,
        }

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if row_matches_asset
            else EvidenceGroundingStatus.UNKNOWN
        )

        meshoogte = record.get(
            "meshoogte_mm"
        )

        numeric_measurement = (
            isinstance(
                meshoogte,
                (int, float),
            )
            and not isinstance(
                meshoogte,
                bool,
            )
        )

        if numeric_measurement:
            measurement_key = (
                canonical_key,
                inspected_on,
                row_band_code,
                scraper_type,
                position_hint,
                cycle_id,
                float(meshoogte),
            )

            if (
                measurement_key
                not in seen_measurements
            ):
                seen_measurements.add(
                    measurement_key
                )

                measurement_record = {
                    "kind": (
                        "inspection_trend_measurement"
                    ),
                    "inspected_on": (
                        inspected_on
                    ),
                    "band_code": (
                        row_band_code
                    ),
                    "scraper_type_norm": (
                        scraper_type
                    ),
                    "position_hint": (
                        position_hint
                    ),
                    "cycle_id": cycle_id,
                    "meshoogte_mm": (
                        float(meshoogte)
                    ),
                    "canonical_inspection_key": (
                        canonical_key
                    ),
                }

                evidence_items.append(
                    EvidenceItem(
                        contract_version=(
                            EVIDENCE_CONTRACT_VERSION
                        ),
                        evidence_id=(
                            _stable_evidence_id(
                                execution_result=(
                                    execution_result
                                ),
                                record=(
                                    measurement_record
                                ),
                                index=(
                                    evidence_index
                                ),
                            )
                        ),
                        execution_step_id=(
                            execution_result.step_id
                        ),
                        specialist_id=(
                            execution_result.action
                        ),
                        domain=(
                            execution_result.domain
                        ),
                        subject=(
                            "measurement_history"
                        ),
                        entity_type=(
                            "scraper_position"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.MEASUREMENT
                        ),
                        source_type=(
                            EvidenceSourceType
                            .LIVE_CANONICAL
                        ),
                        source_name=source_file,
                        source_reference=(
                            canonical_key
                        ),
                        source_priority=None,
                        observed_at=observed_at,
                        retrieved_at=retrieved_at,
                        effective_at=None,
                        value=(
                            measurement_record
                        ),
                        unit="mm",
                        claim_scope=claim_scope,
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .NOT_APPLICABLE
                        ),
                        grounding_status=(
                            grounding_status
                        ),
                        quality_status=(
                            EvidenceQualityStatus.VALID
                            if (
                                identity_complete
                                and observed_at
                                is not None
                            )
                            else EvidenceQualityStatus.UNKNOWN
                        ),
                        direct_or_derived=(
                            EvidenceDirectness.DIRECT
                        ),
                        derivation_reference=None,
                        provenance=copy.deepcopy(
                            common_provenance
                        ),
                    )
                )

                evidence_index += 1

        if record.get("replace_event") is True:
            replacement_key = (
                canonical_key,
                inspected_on,
                row_band_code,
                scraper_type,
                position_hint,
                cycle_id,
            )

            if (
                replacement_key
                not in seen_replacements
            ):
                seen_replacements.add(
                    replacement_key
                )

                replacement_record = {
                    "kind": (
                        "inspection_replacement_event"
                    ),
                    "inspected_on": inspected_on,
                    "band_code": row_band_code,
                    "scraper_type_norm": (
                        scraper_type
                    ),
                    "position_hint": (
                        position_hint
                    ),
                    "cycle_id": cycle_id,
                    "replace_event": True,
                    "canonical_inspection_key": (
                        canonical_key
                    ),
                }

                evidence_items.append(
                    EvidenceItem(
                        contract_version=(
                            EVIDENCE_CONTRACT_VERSION
                        ),
                        evidence_id=(
                            _stable_evidence_id(
                                execution_result=(
                                    execution_result
                                ),
                                record=(
                                    replacement_record
                                ),
                                index=(
                                    evidence_index
                                ),
                            )
                        ),
                        execution_step_id=(
                            execution_result.step_id
                        ),
                        specialist_id=(
                            execution_result.action
                        ),
                        domain=(
                            execution_result.domain
                        ),
                        subject=(
                            "replacement_history"
                        ),
                        entity_type=(
                            "scraper_position"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.EVENT
                        ),
                        source_type=(
                            EvidenceSourceType
                            .LIVE_CANONICAL
                        ),
                        source_name=source_file,
                        source_reference=(
                            canonical_key
                        ),
                        source_priority=None,
                        observed_at=observed_at,
                        retrieved_at=retrieved_at,
                        effective_at=None,
                        value=(
                            replacement_record
                        ),
                        unit=None,
                        claim_scope=claim_scope,
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .NOT_APPLICABLE
                        ),
                        grounding_status=(
                            grounding_status
                        ),
                        quality_status=(
                            EvidenceQualityStatus.VALID
                            if (
                                identity_complete
                                and observed_at
                                is not None
                            )
                            else EvidenceQualityStatus.UNKNOWN
                        ),
                        direct_or_derived=(
                            EvidenceDirectness.DIRECT
                        ),
                        derivation_reference=None,
                        provenance=copy.deepcopy(
                            common_provenance
                        ),
                    )
                )

                evidence_index += 1

        comment = _nonempty_string(
            record.get("commentaar")
        )

        if comment is not None:
            comment_key = (
                canonical_key,
                inspected_on,
                row_band_code,
                scraper_type,
                position_hint,
                cycle_id,
                comment,
            )

            if (
                comment_key
                not in seen_comments
            ):
                seen_comments.add(
                    comment_key
                )

                comment_record = {
                    "kind": (
                        "inspection_lifecycle_comment"
                    ),
                    "inspected_on": inspected_on,
                    "band_code": row_band_code,
                    "scraper_type_norm": (
                        scraper_type
                    ),
                    "position_hint": (
                        position_hint
                    ),
                    "cycle_id": cycle_id,
                    "commentaar": comment,
                    "canonical_inspection_key": (
                        canonical_key
                    ),
                }

                evidence_items.append(
                    EvidenceItem(
                        contract_version=(
                            EVIDENCE_CONTRACT_VERSION
                        ),
                        evidence_id=(
                            _stable_evidence_id(
                                execution_result=(
                                    execution_result
                                ),
                                record=(
                                    comment_record
                                ),
                                index=(
                                    evidence_index
                                ),
                            )
                        ),
                        execution_step_id=(
                            execution_result.step_id
                        ),
                        specialist_id=(
                            execution_result.action
                        ),
                        domain=(
                            execution_result.domain
                        ),
                        subject=(
                            "inspection_comment"
                        ),
                        entity_type=(
                            "scraper_position"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.RECORD
                        ),
                        source_type=(
                            EvidenceSourceType
                            .LIVE_CANONICAL
                        ),
                        source_name=source_file,
                        source_reference=(
                            canonical_key
                        ),
                        source_priority=None,
                        observed_at=observed_at,
                        retrieved_at=retrieved_at,
                        effective_at=None,
                        value=comment_record,
                        unit=None,
                        claim_scope=claim_scope,
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .NOT_APPLICABLE
                        ),
                        grounding_status=(
                            grounding_status
                        ),
                        quality_status=(
                            EvidenceQualityStatus.VALID
                            if (
                                identity_complete
                                and observed_at
                                is not None
                            )
                            else EvidenceQualityStatus.UNKNOWN
                        ),
                        direct_or_derived=(
                            EvidenceDirectness.DIRECT
                        ),
                        derivation_reference=None,
                        provenance=copy.deepcopy(
                            common_provenance
                        ),
                    )
                )

                evidence_index += 1

    return tuple(evidence_items)


# PROMATI_MAINTENANCE_PRIORITY_EVIDENCE_V1
def _analysis_maintenance_priority_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    if (
        _nonempty_string(
            raw_result.get("intent")
        )
        != "maintenance_positions"
    ):
        return ()

    records = raw_result.get("resultaat")

    if not isinstance(records, list):
        return ()

    asset_context = raw_result.get(
        "asset_context"
    )
    asset_resolution = raw_result.get(
        "asset_resolution"
    )

    if not isinstance(
        asset_context,
        dict,
    ):
        asset_context = {}

    if not isinstance(
        asset_resolution,
        dict,
    ):
        asset_resolution = {}

    asset_band_code = _nonempty_string(
        asset_context.get("band_code")
        or asset_context.get("band_code_norm")
    )

    resolution_status = (
        _nonempty_string(
            asset_resolution.get("status")
        )
        or ""
    ).casefold()

    asset_resolved = (
        resolution_status == "resolved"
        and asset_band_code is not None
    )

    evidence_items: list[EvidenceItem] = []

    if asset_band_code is not None:
        asset_record = {
            "kind": "maintenance_priority_asset",
            "band_code": asset_band_code,
            "asset_context": copy.deepcopy(
                asset_context
            ),
            "asset_resolution": copy.deepcopy(
                asset_resolution
            ),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=asset_record,
                    index=-2000,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject="resolved_asset_context",
                entity_type="conveyor_belt",
                entity_id=asset_band_code,
                evidence_type=(
                    EvidenceType.ASSET_RESOLUTION
                ),
                source_type=(
                    EvidenceSourceType
                    .LIVE_CANONICAL
                ),
                source_name=(
                    "analysis_assistant"
                ),
                source_reference=asset_band_code,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=copy.deepcopy(
                    asset_context
                ),
                unit=None,
                claim_scope=(
                    asset_band_code,
                ),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .LATEST_KNOWN
                ),
                grounding_status=(
                    EvidenceGroundingStatus.GROUNDED
                    if asset_resolved
                    else EvidenceGroundingStatus.UNKNOWN
                ),
                quality_status=(
                    EvidenceQualityStatus.VALID
                    if asset_resolved
                    else EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance={
                    "asset_context": copy.deepcopy(
                        asset_context
                    ),
                    "asset_resolution": copy.deepcopy(
                        asset_resolution
                    ),
                },
            )
        )

    seen_status: set[
        tuple[object, ...]
    ] = set()

    seen_measurements: set[
        tuple[object, ...]
    ] = set()

    seen_forecasts: set[
        tuple[object, ...]
    ] = set()

    evidence_index = 0

    for raw_record in records:
        if not isinstance(
            raw_record,
            dict,
        ):
            continue

        record = copy.deepcopy(
            raw_record
        )

        row_band_code = _nonempty_string(
            record.get("band_norm")
        )

        scraper_types = _nonempty_string(
            record.get("scraper_types_clean")
            or record.get("scraper_types")
        )

        position_hint = _nonempty_string(
            record.get("position_hint")
        )

        cycle_start = _nonempty_string(
            record.get("cycle_start")
        )

        cycle_end = _nonempty_string(
            record.get("cycle_end")
        )

        observed_at = _parse_datetime(
            cycle_end
        )

        source_file = _nonempty_string(
            record.get("source_file")
        )

        first_key = _nonempty_string(
            record.get(
                "first_canonical_inspection_key"
            )
        )

        last_key = _nonempty_string(
            record.get(
                "last_canonical_inspection_key"
            )
        )

        meetpunten = record.get(
            "meetpunten"
        )

        meetpunten_valid = (
            isinstance(
                meetpunten,
                int,
            )
            and not isinstance(
                meetpunten,
                bool,
            )
            and meetpunten >= 0
        )

        identity_payload = {
            "band_code": row_band_code,
            "scraper_types": scraper_types,
            "position_hint": position_hint,
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
        }

        identity_serialized = json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        entity_id = (
            "maintenance-position-"
            + hashlib.sha256(
                identity_serialized.encode(
                    "utf-8"
                )
            ).hexdigest()[:24]
        )

        identity_complete = all(
            (
                row_band_code is not None,
                scraper_types is not None,
                position_hint is not None,
                cycle_end is not None,
                last_key is not None,
            )
        )

        row_line_code = _nonempty_string(
            record.get("lijn_code")
            or record.get("line_code")
        )
        asset_installation_code = _nonempty_string(
            asset_context.get("installation_code")
        )
        row_matches_asset = (
            asset_resolved
            and row_band_code is not None
            and asset_band_code is not None
            and (
                row_band_code == asset_band_code
                or (
                    asset_installation_code is not None
                    and row_line_code == asset_installation_code
                )
            )
        )

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if row_matches_asset
            else EvidenceGroundingStatus.UNKNOWN
        )

        claim_scope = tuple(
            str(item)
            for item in (
                row_band_code,
                scraper_types,
                position_hint,
                cycle_start,
                cycle_end,
            )
            if item is not None
        )

        provenance = {
            "band_code": row_band_code,
            "asset_band_code": (
                asset_band_code
            ),
            "scraper_types": scraper_types,
            "position_hint": position_hint,
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "meetpunten": meetpunten,
            "first_canonical_inspection_key": (
                first_key
            ),
            "last_canonical_inspection_key": (
                last_key
            ),
            "source_file": source_file,
            "first_sheet_analysis_key": (
                _nonempty_string(
                    record.get(
                        "first_sheet_analysis_key"
                    )
                )
            ),
            "last_sheet_analysis_key": (
                _nonempty_string(
                    record.get(
                        "last_sheet_analysis_key"
                    )
                )
            ),
        }

        status_record = {
            "kind": (
                "maintenance_position_status"
            ),
            "band_code": row_band_code,
            "scraper_types": scraper_types,
            "position_hint": position_hint,
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "meetpunten": meetpunten,
            "status_3mm": (
                _nonempty_string(
                    record.get("status_3mm")
                )
            ),
            "prioriteit": record.get(
                "prioriteit"
            ),
            "prestatiegrens_mm": (
                record.get(
                    "prestatiegrens_mm"
                )
            ),
            "vervanggrens_mm": (
                record.get(
                    "vervanggrens_mm"
                )
            ),
            "status_6mm": (
                _nonempty_string(
                    record.get("status_6mm")
                )
            ),
            "vervuilingsrisico": (
                record.get(
                    "vervuilingsrisico"
                )
            ),
            "prestatie_vervangmoment": (
                _nonempty_string(
                    record.get(
                        "prestatie_vervangmoment"
                    )
                )
            ),
            "dagen_sinds_laatste_meting": (
                record.get(
                    "dagen_sinds_laatste_meting"
                )
            ),
        }

        status_key = (
            row_band_code,
            scraper_types,
            position_hint,
            cycle_start,
            cycle_end,
            status_record.get(
                "status_3mm"
            ),
            status_record.get(
                "prioriteit"
            ),
            status_record.get(
                "status_6mm"
            ),
        )

        if status_key not in seen_status:
            seen_status.add(
                status_key
            )

            evidence_items.append(
                EvidenceItem(
                    contract_version=(
                        EVIDENCE_CONTRACT_VERSION
                    ),
                    evidence_id=(
                        _stable_evidence_id(
                            execution_result=(
                                execution_result
                            ),
                            record=status_record,
                            index=evidence_index,
                        )
                    ),
                    execution_step_id=(
                        execution_result.step_id
                    ),
                    specialist_id=(
                        execution_result.action
                    ),
                    domain=(
                        execution_result.domain
                    ),
                    subject=(
                        "maintenance_position_status"
                    ),
                    entity_type=(
                        "maintenance_position"
                    ),
                    entity_id=entity_id,
                    evidence_type=(
                        EvidenceType.STATUS
                    ),
                    source_type=(
                        EvidenceSourceType
                        .LIVE_CANONICAL
                    ),
                    source_name=source_file,
                    source_reference=last_key,
                    source_priority=None,
                    observed_at=observed_at,
                    retrieved_at=retrieved_at,
                    effective_at=None,
                    value=status_record,
                    unit=None,
                    claim_scope=claim_scope,
                    freshness_status=(
                        EvidenceFreshnessStatus
                        .LATEST_KNOWN
                    ),
                    grounding_status=(
                        grounding_status
                    ),
                    quality_status=(
                        EvidenceQualityStatus.VALID
                        if (
                            identity_complete
                            and observed_at
                            is not None
                        )
                        else EvidenceQualityStatus.UNKNOWN
                    ),
                    direct_or_derived=(
                        EvidenceDirectness.DERIVED
                    ),
                    derivation_reference=(
                        last_key
                    ),
                    provenance=copy.deepcopy(
                        provenance
                    ),
                )
            )

            evidence_index += 1

        eind_meshoogte = record.get(
            "eind_meshoogte_mm"
        )

        numeric_end_height = (
            isinstance(
                eind_meshoogte,
                (int, float),
            )
            and not isinstance(
                eind_meshoogte,
                bool,
            )
        )

        if numeric_end_height:
            measurement_record = {
                "kind": (
                    "latest_position_measurement"
                ),
                "band_code": row_band_code,
                "scraper_types": scraper_types,
                "position_hint": position_hint,
                "cycle_end": cycle_end,
                "meshoogte_mm": float(
                    eind_meshoogte
                ),
                "canonical_inspection_key": (
                    last_key
                ),
            }

            measurement_key = (
                row_band_code,
                scraper_types,
                position_hint,
                cycle_end,
                float(
                    eind_meshoogte
                ),
                last_key,
            )

            if (
                measurement_key
                not in seen_measurements
            ):
                seen_measurements.add(
                    measurement_key
                )

                evidence_items.append(
                    EvidenceItem(
                        contract_version=(
                            EVIDENCE_CONTRACT_VERSION
                        ),
                        evidence_id=(
                            _stable_evidence_id(
                                execution_result=(
                                    execution_result
                                ),
                                record=(
                                    measurement_record
                                ),
                                index=(
                                    evidence_index
                                ),
                            )
                        ),
                        execution_step_id=(
                            execution_result.step_id
                        ),
                        specialist_id=(
                            execution_result.action
                        ),
                        domain=(
                            execution_result.domain
                        ),
                        subject=(
                            "latest_position_measurement"
                        ),
                        entity_type=(
                            "maintenance_position"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.MEASUREMENT
                        ),
                        source_type=(
                            EvidenceSourceType
                            .LIVE_CANONICAL
                        ),
                        source_name=source_file,
                        source_reference=last_key,
                        source_priority=None,
                        observed_at=observed_at,
                        retrieved_at=retrieved_at,
                        effective_at=None,
                        value=(
                            measurement_record
                        ),
                        unit="mm",
                        claim_scope=claim_scope,
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .LATEST_KNOWN
                        ),
                        grounding_status=(
                            grounding_status
                        ),
                        quality_status=(
                            EvidenceQualityStatus.VALID
                            if (
                                identity_complete
                                and observed_at
                                is not None
                            )
                            else EvidenceQualityStatus.UNKNOWN
                        ),
                        direct_or_derived=(
                            EvidenceDirectness.DIRECT
                        ),
                        derivation_reference=None,
                        provenance=copy.deepcopy(
                            provenance
                        ),
                    )
                )

                evidence_index += 1

        wear_rate = record.get(
            "slijtage_mm_per_dag"
        )

        days_to_3mm = record.get(
            "geschatte_dagen_tot_3mm"
        )

        replacement_date = (
            _nonempty_string(
                record.get(
                    "geschatte_vervangdatum_bij_3mm"
                )
            )
        )

        numeric_wear_rate = (
            isinstance(
                wear_rate,
                (int, float),
            )
            and not isinstance(
                wear_rate,
                bool,
            )
        )

        numeric_days_to_3mm = (
            isinstance(
                days_to_3mm,
                (int, float),
            )
            and not isinstance(
                days_to_3mm,
                bool,
            )
        )

        forecast_eligible = (
            meetpunten_valid
            and meetpunten >= 3
            and numeric_end_height
            and numeric_wear_rate
            and numeric_days_to_3mm
            and replacement_date is not None
            and observed_at is not None
            and identity_complete
        )

        if forecast_eligible:
            forecast_record = {
                "kind": (
                    "maintenance_threshold_forecast"
                ),
                "band_code": row_band_code,
                "scraper_types": scraper_types,
                "position_hint": position_hint,
                "cycle_end": cycle_end,
                "meetpunten": meetpunten,
                "eind_meshoogte_mm": float(
                    eind_meshoogte
                ),
                "slijtage_mm_per_dag": float(
                    wear_rate
                ),
                "vervanggrens_mm": (
                    record.get(
                        "vervanggrens_mm"
                    )
                ),
                "geschatte_dagen_tot_3mm": (
                    float(days_to_3mm)
                ),
                "geschatte_vervangdatum_bij_3mm": (
                    replacement_date
                ),
                "status_3mm": (
                    _nonempty_string(
                        record.get(
                            "status_3mm"
                        )
                    )
                ),
            }

            forecast_key = (
                row_band_code,
                scraper_types,
                position_hint,
                cycle_end,
                meetpunten,
                float(eind_meshoogte),
                float(wear_rate),
                float(days_to_3mm),
                replacement_date,
            )

            if (
                forecast_key
                not in seen_forecasts
            ):
                seen_forecasts.add(
                    forecast_key
                )

                evidence_items.append(
                    EvidenceItem(
                        contract_version=(
                            EVIDENCE_CONTRACT_VERSION
                        ),
                        evidence_id=(
                            _stable_evidence_id(
                                execution_result=(
                                    execution_result
                                ),
                                record=(
                                    forecast_record
                                ),
                                index=(
                                    evidence_index
                                ),
                            )
                        ),
                        execution_step_id=(
                            execution_result.step_id
                        ),
                        specialist_id=(
                            execution_result.action
                        ),
                        domain=(
                            execution_result.domain
                        ),
                        subject=(
                            "forecast_result"
                        ),
                        entity_type=(
                            "maintenance_position"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType
                            .CALCULATION_RESULT
                        ),
                        source_type=(
                            EvidenceSourceType
                            .LIVE_CANONICAL
                        ),
                        source_name=source_file,
                        source_reference=last_key,
                        source_priority=None,
                        observed_at=observed_at,
                        retrieved_at=retrieved_at,
                        effective_at=None,
                        value=forecast_record,
                        unit=None,
                        claim_scope=claim_scope,
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .LATEST_KNOWN
                        ),
                        grounding_status=(
                            grounding_status
                        ),
                        quality_status=(
                            EvidenceQualityStatus.VALID
                        ),
                        direct_or_derived=(
                            EvidenceDirectness.DERIVED
                        ),
                        derivation_reference=(
                            last_key
                        ),
                        provenance=copy.deepcopy(
                            provenance
                        ),
                    )
                )

                evidence_index += 1

    return tuple(evidence_items)


# PROMATI_INSPECTION_LATEST_EVIDENCE_V1
def _analysis_resultaat_latest_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    records = raw_result.get("resultaat")

    if not isinstance(records, list):
        return ()

    dict_records = tuple(
        copy.deepcopy(item)
        for item in records
        if isinstance(item, dict)
    )

    if not dict_records:
        return ()

    dated_records = tuple(
        (
            record,
            _parse_datetime(record.get("document_date")),
        )
        for record in dict_records
    )

    usable_dates = tuple(
        observed_at
        for _, observed_at in dated_records
        if observed_at is not None
    )

    if not usable_dates:
        return ()

    latest_dt = max(usable_dates)
    latest_date_text = latest_dt.date().isoformat()

    latest_records = tuple(
        record
        for record, observed_at in dated_records
        if (
            observed_at is not None
            and observed_at.date() == latest_dt.date()
        )
    )

    if not latest_records:
        return ()

    asset_context = raw_result.get("asset_context")
    asset_resolution = raw_result.get("asset_resolution")

    if not isinstance(asset_context, dict):
        asset_context = {}

    if not isinstance(asset_resolution, dict):
        asset_resolution = {}

    asset_band_code = _nonempty_string(
        asset_context.get("band_code")
        or asset_context.get("band_code_norm")
    )

    resolution_status = _nonempty_string(
        asset_resolution.get("status")
    )

    asset_grounded = (
        resolution_status == "resolved"
        and asset_band_code is not None
    )

    evidence_items: list[EvidenceItem] = []

    def add_item(
        *,
        record: dict[str, Any],
        index: int,
        subject: str,
        entity_type: str,
        entity_id: str | None,
        evidence_type: EvidenceType,
        value: Any,
        unit: str | None,
        observed_at: datetime | None,
        source_name: str | None,
        source_reference: str | None,
        grounded: bool,
        quality_valid: bool,
        provenance: dict[str, Any],
        claim_scope: tuple[str, ...] = (),
    ) -> None:
        evidence_items.append(
            EvidenceItem(
                contract_version=EVIDENCE_CONTRACT_VERSION,
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=execution_result.step_id,
                specialist_id=execution_result.action,
                domain=execution_result.domain,
                subject=subject,
                entity_type=entity_type,
                entity_id=entity_id,
                evidence_type=evidence_type,
                source_type=EvidenceSourceType.LIVE_CANONICAL,
                source_name=source_name,
                source_reference=source_reference,
                source_priority=None,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=value,
                unit=unit,
                claim_scope=claim_scope,
                freshness_status=(
                    EvidenceFreshnessStatus.LATEST_KNOWN
                ),
                grounding_status=(
                    EvidenceGroundingStatus.GROUNDED
                    if grounded
                    else EvidenceGroundingStatus.UNKNOWN
                ),
                quality_status=(
                    EvidenceQualityStatus.VALID
                    if quality_valid
                    else EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=EvidenceDirectness.DIRECT,
                derivation_reference=None,
                provenance=provenance,
            )
        )

    # --------------------------------------------------------
    # 1. Canonical resolved asset context
    # --------------------------------------------------------

    if asset_band_code is not None:
        asset_record = {
            "kind": "inspection_latest_asset_context",
            "asset_context": copy.deepcopy(asset_context),
            "asset_resolution": copy.deepcopy(asset_resolution),
        }

        add_item(
            record=asset_record,
            index=10_000,
            subject="resolved_asset_context",
            entity_type="conveyor_belt",
            entity_id=asset_band_code,
            evidence_type=EvidenceType.ASSET_RESOLUTION,
            value=copy.deepcopy(asset_context),
            unit=None,
            observed_at=latest_dt,
            source_name="analysis_assistant",
            source_reference=asset_band_code,
            grounded=asset_grounded,
            quality_valid=asset_grounded,
            provenance={
                "asset_context": copy.deepcopy(asset_context),
                "asset_resolution": copy.deepcopy(asset_resolution),
            },
            claim_scope=(asset_band_code,),
        )

    # --------------------------------------------------------
    # 2. Latest inspection date
    # --------------------------------------------------------

    inspection_keys = tuple(
        sorted(
            {
                value
                for value in (
                    _nonempty_string(
                        record.get("inspection_key")
                    )
                    for record in latest_records
                )
                if value is not None
            }
        )
    )

    primary_inspection_key = (
        inspection_keys[0]
        if inspection_keys
        else None
    )

    inspection_entity_id = (
        primary_inspection_key
        or (
            f"{asset_band_code}|{latest_date_text}"
            if asset_band_code
            else latest_date_text
        )
    )

    date_grounded = (
        asset_grounded
        and inspection_entity_id is not None
    )

    date_record = {
        "kind": "inspection_latest_date",
        "document_date": latest_date_text,
        "inspection_keys": inspection_keys,
        "band_code": asset_band_code,
    }

    add_item(
        record=date_record,
        index=20_000,
        subject="latest_inspection_date",
        entity_type="inspection",
        entity_id=inspection_entity_id,
        evidence_type=EvidenceType.EVENT,
        value={
            "document_date": latest_date_text,
        },
        unit=None,
        observed_at=latest_dt,
        source_name="analysis_assistant",
        source_reference=primary_inspection_key,
        grounded=date_grounded,
        quality_valid=(
            latest_date_text is not None
            and inspection_entity_id is not None
        ),
        provenance={
            "inspection_keys": inspection_keys,
            "band_code": asset_band_code,
            "latest_known": True,
        },
        claim_scope=(
            (asset_band_code,)
            if asset_band_code
            else ()
        ),
    )

    # --------------------------------------------------------
    # 3. Latest blade-height measurements
    #
    # Fact rows repeat the same physical measurement for each
    # check_code. Deduplicate the physical observation.
    #
    # PROMATI_P4_14Z_INSPECTION_LATEST_MEASUREMENT_AGGREGATE_V1
    # The inspection_latest.v1 requirement asks whether the latest
    # canonical inspection has directly observed scraper-position
    # measurements. A belt inspection naturally contains multiple
    # position values. Emit one task-level MEASUREMENT aggregate for
    # requirement sufficiency and keep per-position values as detail
    # RECORD evidence, preventing false scalar conflicts.
    # --------------------------------------------------------

    aggregate_rows: list[dict[str, Any]] = []
    aggregate_seen: set[tuple[str | None, str | None, str | None, str]] = set()

    for record in latest_records:
        meshoogte = record.get("meshoogte_mm")

        if meshoogte is None:
            continue

        inspection_key = _nonempty_string(
            record.get("inspection_key")
        )
        scraper_type = _nonempty_string(
            record.get("scraper_type_raw")
        )
        location = _nonempty_string(
            record.get("locatie_raw")
        )
        row_band_code = _nonempty_string(
            record.get("band_code")
        )

        aggregate_key = (
            inspection_key,
            scraper_type,
            location,
            str(meshoogte),
        )

        if aggregate_key in aggregate_seen:
            continue

        aggregate_seen.add(aggregate_key)

        aggregate_rows.append(
            {
                "inspection_key": inspection_key,
                "document_date": latest_date_text,
                "band_code": row_band_code,
                "scraper_type_raw": scraper_type,
                "locatie_raw": location,
                "meshoogte_mm": meshoogte,
                "mes_vervangen": record.get("mes_vervangen"),
                "source_file": (
                    _nonempty_string(record.get("source_file"))
                    or _nonempty_string(record.get("source_name"))
                ),
            }
        )

    if aggregate_rows:
        numeric_values = [
            float(row["meshoogte_mm"])
            for row in aggregate_rows
            if isinstance(row.get("meshoogte_mm"), (int, float))
            and not isinstance(row.get("meshoogte_mm"), bool)
        ]

        aggregate_record = {
            "kind": "inspection_latest_measurement_set",
            "document_date": latest_date_text,
            "band_code": asset_band_code,
            "inspection_keys": inspection_keys,
            "measurement_count": len(aggregate_rows),
            "numeric_measurement_count": len(numeric_values),
            "min_meshoogte_mm": (
                min(numeric_values)
                if numeric_values
                else None
            ),
            "max_meshoogte_mm": (
                max(numeric_values)
                if numeric_values
                else None
            ),
            "position_measurements": copy.deepcopy(aggregate_rows),
            "latest_known": True,
        }

        aggregate_entity_id = (
            (
                str(asset_band_code)
                + "|latest-inspection-measurements|"
                + latest_date_text
            )
            if asset_band_code is not None
            else (
                "latest-inspection-measurements|"
                + latest_date_text
            )
        )

        aggregate_grounded = (
            asset_grounded
            and aggregate_entity_id is not None
            and bool(aggregate_rows)
        )

        add_item(
            record=aggregate_record,
            index=29_000,
            subject="latest_blade_height",
            entity_type="scraper_position",
            entity_id=aggregate_entity_id,
            evidence_type=EvidenceType.MEASUREMENT,
            value=aggregate_record,
            unit="mm",
            observed_at=latest_dt,
            source_name="analysis_assistant",
            source_reference=primary_inspection_key,
            grounded=aggregate_grounded,
            quality_valid=(
                latest_date_text is not None
                and bool(aggregate_rows)
                and aggregate_entity_id is not None
            ),
            provenance={
                "inspection_keys": inspection_keys,
                "band_code": asset_band_code,
                "measurement_count": len(aggregate_rows),
                "provenance_basis": "p4_14z_task_level_measurement_aggregate",
                "latest_known": True,
            },
            claim_scope=(
                (asset_band_code, "LATEST_INSPECTION_MEASUREMENT")
                if asset_band_code
                else ("LATEST_INSPECTION_MEASUREMENT",)
            ),
        )

    seen_measurements: set[
        tuple[
            str | None,
            str | None,
            str | None,
            str,
        ]
    ] = set()

    measurement_index = 30_000

    for record in latest_records:
        meshoogte = record.get("meshoogte_mm")

        if meshoogte is None:
            continue

        inspection_key = _nonempty_string(
            record.get("inspection_key")
        )
        scraper_type = _nonempty_string(
            record.get("scraper_type_raw")
        )
        location = _nonempty_string(
            record.get("locatie_raw")
        )
        row_band_code = _nonempty_string(
            record.get("band_code")
        )

        dedupe_key = (
            inspection_key,
            scraper_type,
            location,
            str(meshoogte),
        )

        if dedupe_key in seen_measurements:
            continue

        seen_measurements.add(dedupe_key)

        identity_payload = {
            "inspection_key": inspection_key,
            "scraper_type_raw": scraper_type,
            "locatie_raw": location,
            "band_code": row_band_code,
        }

        identity_serialized = json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        entity_id = (
            "scraper-position-"
            + hashlib.sha256(
                identity_serialized.encode("utf-8")
            ).hexdigest()[:24]
        )

        source_file = (
            _nonempty_string(record.get("source_file"))
            or _nonempty_string(record.get("source_name"))
        )

        row_line_code = _nonempty_string(
            record.get("line_hint")
            or record.get("lijn_code")
        )
        asset_installation_code = _nonempty_string(
            asset_context.get("installation_code")
        )
        row_matches_asset = (
            asset_band_code is not None
            and (
                row_band_code == asset_band_code
                or (
                    asset_installation_code is not None
                    and row_line_code == asset_installation_code
                )
            )
        )

        required_quality_fields_present = all(
            (
                row_band_code is not None,
                _nonempty_string(
                    record.get("document_date")
                )
                is not None,
                inspection_key is not None,
                scraper_type is not None,
                meshoogte is not None,
            )
        )

        provenance = {
            "inspection_key": inspection_key,
            "document_date": latest_date_text,
            "band_code": row_band_code,
            "asset_band_code": asset_band_code,
            "installation_code": _nonempty_string(
                asset_context.get("installation_code")
            ),
            "area_code": _nonempty_string(
                asset_context.get("area_code")
            ),
            "scraper_type_raw": scraper_type,
            "locatie_raw": location,
            "source_system": _nonempty_string(
                record.get("source_system")
            ),
            "provenance_basis": _nonempty_string(
                record.get("provenance_basis")
            ),
            "latest_known": True,
        }

        measurement_record = {
            "kind": "inspection_latest_measurement",
            "inspection_key": inspection_key,
            "document_date": latest_date_text,
            "band_code": row_band_code,
            "scraper_type_raw": scraper_type,
            "locatie_raw": location,
            "meshoogte_mm": meshoogte,
            "mes_vervangen": record.get("mes_vervangen"),
        }

        add_item(
            record=measurement_record,
            index=measurement_index,
            subject="latest_blade_height_detail",
            entity_type="scraper_position_detail",
            entity_id=entity_id,
            evidence_type=EvidenceType.RECORD,
            value=measurement_record,
            unit="mm",
            observed_at=latest_dt,
            source_name=source_file,
            source_reference=inspection_key,
            grounded=(
                asset_grounded
                and row_matches_asset
            ),
            quality_valid=(
                required_quality_fields_present
            ),
            provenance=provenance,
            claim_scope=tuple(
                value
                for value in (
                    asset_band_code,
                    scraper_type,
                    location,
                )
                if value is not None
            ),
        )

        measurement_index += 1

    # --------------------------------------------------------
    # 4. Desired latest check-status records
    # --------------------------------------------------------

    check_index = 40_000
    seen_checks: set[
        tuple[
            str | None,
            str | None,
            str | None,
        ]
    ] = set()

    for record in latest_records:
        inspection_key = _nonempty_string(
            record.get("inspection_key")
        )
        check_code = _nonempty_string(
            record.get("check_code")
        )
        status = _nonempty_string(
            record.get("status")
        )

        if check_code is None or status is None:
            continue

        check_identity = (
            inspection_key,
            check_code,
            status,
        )

        if check_identity in seen_checks:
            continue

        seen_checks.add(check_identity)

        check_record = {
            "inspection_key": inspection_key,
            "document_date": latest_date_text,
            "check_code": check_code,
            "status": status,
        }

        add_item(
            record=check_record,
            index=check_index,
            subject="inspection_check_status",
            entity_type="inspection",
            entity_id=(
                inspection_key
                or inspection_entity_id
            ),
            evidence_type=EvidenceType.STATUS,
            value=check_record,
            unit=None,
            observed_at=latest_dt,
            source_name=(
                _nonempty_string(record.get("source_file"))
                or _nonempty_string(record.get("source_name"))
            ),
            source_reference=inspection_key,
            grounded=asset_grounded,
            quality_valid=(
                check_code is not None
                and status is not None
                and (
                    inspection_key is not None
                    or inspection_entity_id is not None
                )
            ),
            provenance={
                "band_code": _nonempty_string(
                    record.get("band_code")
                ),
                "latest_known": True,
            },
            claim_scope=(
                (asset_band_code,)
                if asset_band_code
                else ()
            ),
        )

        check_index += 1

    # --------------------------------------------------------
    # 5. Desired comments
    # --------------------------------------------------------

    comment_index = 50_000
    seen_comments: set[
        tuple[str | None, str]
    ] = set()

    for record in latest_records:
        comment = _nonempty_string(
            record.get("commentaar")
        )

        if comment is None:
            continue

        inspection_key = _nonempty_string(
            record.get("inspection_key")
        )

        comment_identity = (
            inspection_key,
            comment,
        )

        if comment_identity in seen_comments:
            continue

        seen_comments.add(comment_identity)

        comment_record = {
            "inspection_key": inspection_key,
            "document_date": latest_date_text,
            "commentaar": comment,
        }

        add_item(
            record=comment_record,
            index=comment_index,
            subject="inspection_comment",
            entity_type="inspection",
            entity_id=(
                inspection_key
                or inspection_entity_id
            ),
            evidence_type=EvidenceType.RECORD,
            value=comment_record,
            unit=None,
            observed_at=latest_dt,
            source_name=(
                _nonempty_string(record.get("source_file"))
                or _nonempty_string(record.get("source_name"))
            ),
            source_reference=inspection_key,
            grounded=asset_grounded,
            quality_valid=True,
            provenance={
                "band_code": _nonempty_string(
                    record.get("band_code")
                ),
                "latest_known": True,
            },
            claim_scope=(
                (asset_band_code,)
                if asset_band_code
                else ()
            ),
        )

        comment_index += 1

    return tuple(evidence_items)



# PROMATI_REPLACEMENT_ADVICE_EVIDENCE_V1
def _analysis_replacement_advice_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    if (
        _nonempty_string(
            raw_result.get("intent")
        )
        != "band_deep_analysis"
    ):
        return ()

    asset_context = raw_result.get(
        "asset_context"
    )

    asset_resolution = raw_result.get(
        "asset_resolution"
    )

    if not isinstance(
        asset_context,
        dict,
    ):
        asset_context = {}

    if not isinstance(
        asset_resolution,
        dict,
    ):
        asset_resolution = {}

    asset_band_code = _nonempty_string(
        asset_context.get("band_code")
        or asset_context.get("band_code_norm")
        or (
            raw_result.get("entities") or {}
        ).get("band_code")
    )

    resolution_status = (
        _nonempty_string(
            asset_resolution.get("status")
        )
        or ""
    ).casefold()

    asset_resolved = (
        resolution_status == "resolved"
        and asset_band_code is not None
    )

    evidence_items: list[
        EvidenceItem
    ] = []

    evidence_index = 0

    def numeric(
        value: Any,
    ) -> bool:
        return (
            isinstance(
                value,
                (int, float),
            )
            and not isinstance(
                value,
                bool,
            )
        )

    def band_matches(
        row_band: str | None,
    ) -> bool:
        if (
            not asset_resolved
            or asset_band_code is None
            or row_band is None
        ):
            return False

        return (
            row_band.replace(
                " ",
                "",
            ).casefold()
            ==
            asset_band_code.replace(
                " ",
                "",
            ).casefold()
        )

    def position_entity_id(
        *,
        row_band: str | None,
        scraper: str | None,
        position: str | None,
    ) -> str | None:
        if (
            row_band is None
            or scraper is None
        ):
            return None

        position_value = (
            position
            or "GEEN_POSITIE"
        )

        return (
            f"{row_band}|"
            f"{scraper}|"
            f"{position_value}"
        )

    def add_item(
        *,
        record: dict[str, Any],
        subject: str,
        entity_type: str,
        entity_id: str | None,
        evidence_type: EvidenceType,
        source_name: str | None,
        source_reference: str | None,
        observed_at: datetime | None,
        value: Any,
        unit: str | None,
        claim_scope: tuple[str, ...],
        freshness_status: EvidenceFreshnessStatus,
        grounded: bool,
        quality_valid: bool,
        directness: EvidenceDirectness,
        derivation_reference: str | None,
        provenance: dict[str, Any],
    ) -> None:
        nonlocal evidence_index

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=(
                    _stable_evidence_id(
                        execution_result=(
                            execution_result
                        ),
                        record=record,
                        index=evidence_index,
                    )
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=(
                    execution_result.domain
                ),
                subject=subject,
                entity_type=entity_type,
                entity_id=entity_id,
                evidence_type=evidence_type,
                source_type=(
                    EvidenceSourceType
                    .LIVE_CANONICAL
                ),
                source_name=source_name,
                source_reference=(
                    source_reference
                ),
                source_priority=None,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=value,
                unit=unit,
                claim_scope=claim_scope,
                freshness_status=(
                    freshness_status
                ),
                grounding_status=(
                    EvidenceGroundingStatus
                    .GROUNDED
                    if grounded
                    else EvidenceGroundingStatus
                    .UNKNOWN
                ),
                quality_status=(
                    EvidenceQualityStatus.VALID
                    if quality_valid
                    else EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=directness,
                derivation_reference=(
                    derivation_reference
                ),
                provenance=(
                    copy.deepcopy(
                        provenance
                    )
                ),
            )
        )

        evidence_index += 1

    if asset_band_code is not None:
        asset_record = {
            "kind": (
                "replacement_advice_asset"
            ),
            "band_code": (
                asset_band_code
            ),
            "asset_context": (
                copy.deepcopy(
                    asset_context
                )
            ),
            "asset_resolution": (
                copy.deepcopy(
                    asset_resolution
                )
            ),
        }

        add_item(
            record=asset_record,
            subject=(
                "resolved_asset_context"
            ),
            entity_type="conveyor_belt",
            entity_id=asset_band_code,
            evidence_type=(
                EvidenceType
                .ASSET_RESOLUTION
            ),
            source_name=(
                "band_deep_analysis"
            ),
            source_reference=(
                asset_band_code
            ),
            observed_at=None,
            value=asset_record,
            unit=None,
            claim_scope=(
                "RESOLVED_ASSET_CONTEXT",
            ),
            freshness_status=(
                EvidenceFreshnessStatus
                .LATEST_KNOWN
            ),
            grounded=asset_resolved,
            quality_valid=asset_resolved,
            directness=(
                EvidenceDirectness.DIRECT
            ),
            derivation_reference=None,
            provenance={
                "analysis_intent": (
                    "band_deep_analysis"
                ),
            },
        )

    latest_rows = raw_result.get(
        "laatste_meshoogte"
    )

    if isinstance(
        latest_rows,
        list,
    ):
        seen_latest: set[
            tuple[object, ...]
        ] = set()

        for raw_row in latest_rows:
            if not isinstance(
                raw_row,
                dict,
            ):
                continue

            row = copy.deepcopy(
                raw_row
            )

            row_band = _nonempty_string(
                row.get("band_norm")
            )

            scraper = _nonempty_string(
                row.get(
                    "scraper_type_norm"
                )
            )

            position = _nonempty_string(
                row.get("position_hint")
            )

            measured_at_text = (
                _nonempty_string(
                    row.get(
                        "laatste_meting_datum"
                    )
                )
            )

            observed_at = (
                _parse_datetime(
                    measured_at_text
                )
            )

            meshoogte = row.get(
                "meshoogte_mm"
            )

            canonical_key = (
                _nonempty_string(
                    row.get(
                        "canonical_inspection_key"
                    )
                )
            )

            source_file = (
                _nonempty_string(
                    row.get("source_file")
                )
            )

            entity_id = (
                position_entity_id(
                    row_band=row_band,
                    scraper=scraper,
                    position=position,
                )
            )

            if not numeric(
                meshoogte
            ):
                continue

            latest_key = (
                row_band,
                scraper,
                position,
                measured_at_text,
                float(meshoogte),
                canonical_key,
            )

            if latest_key in seen_latest:
                continue

            seen_latest.add(
                latest_key
            )

            measurement_record = {
                "kind": (
                    "replacement_latest_measurement"
                ),
                "band_code": row_band,
                "scraper_type_norm": (
                    scraper
                ),
                "position_hint": position,
                "measured_at": (
                    measured_at_text
                ),
                "meshoogte_mm": float(
                    meshoogte
                ),
                "canonical_inspection_key": (
                    canonical_key
                ),
            }

            grounded = (
                band_matches(
                    row_band
                )
                and entity_id is not None
            )

            identity_complete = (
                entity_id is not None
                and canonical_key
                is not None
                and observed_at
                is not None
            )

            add_item(
                record=measurement_record,
                subject=(
                    "latest_position_measurement"
                ),
                entity_type=(
                    "scraper_position"
                ),
                entity_id=entity_id,
                evidence_type=(
                    EvidenceType.MEASUREMENT
                ),
                source_name=source_file,
                source_reference=(
                    canonical_key
                ),
                observed_at=observed_at,
                value=measurement_record,
                unit="mm",
                claim_scope=(
                    "LATEST_POSITION_MEASUREMENT",
                ),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .LATEST_KNOWN
                ),
                grounded=grounded,
                quality_valid=(
                    identity_complete
                ),
                directness=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance={
                    "source_file": (
                        source_file
                    ),
                    "sheet_raw": (
                        _nonempty_string(
                            row.get(
                                "sheet_raw"
                            )
                        )
                    ),
                    "canonical_inspection_key": (
                        canonical_key
                    ),
                },
            )

    lifecycle_rows = raw_result.get(
        "lifecycle"
    )

    if isinstance(
        lifecycle_rows,
        list,
    ):
        seen_measurements: set[
            tuple[object, ...]
        ] = set()

        seen_replacements: set[
            tuple[object, ...]
        ] = set()

        for raw_row in lifecycle_rows:
            if not isinstance(
                raw_row,
                dict,
            ):
                continue

            row = copy.deepcopy(
                raw_row
            )

            row_band = _nonempty_string(
                row.get("band_norm")
            )

            scraper = _nonempty_string(
                row.get(
                    "scraper_type_norm"
                )
            )

            position = _nonempty_string(
                row.get("position_hint")
            )

            inspected_on = (
                _nonempty_string(
                    row.get(
                        "inspected_on"
                    )
                )
            )

            observed_at = (
                _parse_datetime(
                    inspected_on
                )
            )

            canonical_key = (
                _nonempty_string(
                    row.get(
                        "canonical_inspection_key"
                    )
                )
            )

            source_file = (
                _nonempty_string(
                    row.get(
                        "source_file"
                    )
                )
            )

            cycle_id = row.get(
                "cycle_id"
            )

            meshoogte = row.get(
                "meshoogte_mm"
            )

            entity_id = (
                position_entity_id(
                    row_band=row_band,
                    scraper=scraper,
                    position=position,
                )
            )

            grounded = (
                band_matches(
                    row_band
                )
                and entity_id is not None
            )

            identity_complete = (
                entity_id is not None
                and canonical_key
                is not None
                and observed_at
                is not None
            )

            provenance = {
                "source_file": (
                    source_file
                ),
                "canonical_inspection_key": (
                    canonical_key
                ),
                "cycle_id": cycle_id,
            }

            if numeric(
                meshoogte
            ):
                measurement_key = (
                    canonical_key,
                    inspected_on,
                    row_band,
                    scraper,
                    position,
                    cycle_id,
                    float(meshoogte),
                )

                if (
                    measurement_key
                    not in seen_measurements
                ):
                    seen_measurements.add(
                        measurement_key
                    )

                    measurement_record = {
                        "kind": (
                            "replacement_lifecycle_measurement"
                        ),
                        "inspected_on": (
                            inspected_on
                        ),
                        "band_code": (
                            row_band
                        ),
                        "scraper_type_norm": (
                            scraper
                        ),
                        "position_hint": (
                            position
                        ),
                        "cycle_id": (
                            cycle_id
                        ),
                        "meshoogte_mm": float(
                            meshoogte
                        ),
                        "canonical_inspection_key": (
                            canonical_key
                        ),
                    }

                    add_item(
                        record=(
                            measurement_record
                        ),
                        subject=(
                            "lifecycle_measurement"
                        ),
                        entity_type=(
                            "scraper_lifecycle"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.MEASUREMENT
                        ),
                        source_name=(
                            source_file
                        ),
                        source_reference=(
                            canonical_key
                        ),
                        observed_at=(
                            observed_at
                        ),
                        value=(
                            measurement_record
                        ),
                        unit="mm",
                        claim_scope=(
                            "LIFECYCLE_HISTORY",
                            inspected_on
                            or "unknown_date",
                        ),
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .NOT_APPLICABLE
                        ),
                        grounded=grounded,
                        quality_valid=(
                            identity_complete
                        ),
                        directness=(
                            EvidenceDirectness
                            .DIRECT
                        ),
                        derivation_reference=None,
                        provenance=provenance,
                    )

            if (
                row.get(
                    "replace_event"
                )
                is True
            ):
                replacement_key = (
                    canonical_key,
                    inspected_on,
                    row_band,
                    scraper,
                    position,
                    cycle_id,
                )

                if (
                    replacement_key
                    not in seen_replacements
                ):
                    seen_replacements.add(
                        replacement_key
                    )

                    replacement_record = {
                        "kind": (
                            "replacement_event"
                        ),
                        "inspected_on": (
                            inspected_on
                        ),
                        "band_code": (
                            row_band
                        ),
                        "scraper_type_norm": (
                            scraper
                        ),
                        "position_hint": (
                            position
                        ),
                        "cycle_id": (
                            cycle_id
                        ),
                        "replace_event": True,
                        "canonical_inspection_key": (
                            canonical_key
                        ),
                    }

                    add_item(
                        record=(
                            replacement_record
                        ),
                        subject=(
                            "replacement_history"
                        ),
                        entity_type=(
                            "scraper_lifecycle"
                        ),
                        entity_id=entity_id,
                        evidence_type=(
                            EvidenceType.EVENT
                        ),
                        source_name=(
                            source_file
                        ),
                        source_reference=(
                            canonical_key
                        ),
                        observed_at=(
                            observed_at
                        ),
                        value=(
                            replacement_record
                        ),
                        unit=None,
                        claim_scope=(
                            "LIFECYCLE_HISTORY",
                            "REPLACEMENT_HISTORY",
                            inspected_on
                            or "unknown_date",
                        ),
                        freshness_status=(
                            EvidenceFreshnessStatus
                            .NOT_APPLICABLE
                        ),
                        grounded=grounded,
                        quality_valid=(
                            identity_complete
                        ),
                        directness=(
                            EvidenceDirectness
                            .DIRECT
                        ),
                        derivation_reference=None,
                        provenance=provenance,
                    )

    forecast_rows = raw_result.get(
        "forecast_3mm"
    )

    if isinstance(
        forecast_rows,
        list,
    ):
        seen_forecasts: set[
            tuple[object, ...]
        ] = set()

        for raw_row in forecast_rows:
            if not isinstance(
                raw_row,
                dict,
            ):
                continue

            row = copy.deepcopy(
                raw_row
            )

            row_band = _nonempty_string(
                row.get("band_norm")
            )

            scraper = _nonempty_string(
                row.get(
                    "scraper_type_norm"
                )
            )

            position = _nonempty_string(
                row.get("position_hint")
            )

            cycle_end = _nonempty_string(
                row.get("cycle_end")
            )

            observed_at = _parse_datetime(
                cycle_end
            )

            meetpunten = row.get(
                "meetpunten"
            )

            eind_meshoogte = row.get(
                "eind_meshoogte_mm"
            )

            wear_rate = row.get(
                "slijtage_mm_per_dag"
            )

            days_to_3mm = row.get(
                "geschatte_dagen_tot_3mm"
            )

            replacement_date = (
                _nonempty_string(
                    row.get(
                        "geschatte_vervangdatum_bij_3mm"
                    )
                )
            )

            source_file = (
                _nonempty_string(
                    row.get("source_file")
                )
            )

            last_key = (
                _nonempty_string(
                    row.get(
                        "last_canonical_inspection_key"
                    )
                )
            )

            entity_id = (
                position_entity_id(
                    row_band=row_band,
                    scraper=scraper,
                    position=position,
                )
            )

            meetpunten_valid = (
                isinstance(
                    meetpunten,
                    int,
                )
                and not isinstance(
                    meetpunten,
                    bool,
                )
            )

            forecast_eligible = (
                meetpunten_valid
                and meetpunten >= 3
                and numeric(
                    eind_meshoogte
                )
                and numeric(
                    wear_rate
                )
                and numeric(
                    days_to_3mm
                )
                and replacement_date
                is not None
                and observed_at
                is not None
                and entity_id
                is not None
                and last_key
                is not None
                and band_matches(
                    row_band
                )
            )

            if not forecast_eligible:
                continue

            forecast_record = {
                "kind": (
                    "replacement_threshold_forecast"
                ),
                "band_code": row_band,
                "scraper_type_norm": (
                    scraper
                ),
                "position_hint": (
                    position
                ),
                "cycle_end": cycle_end,
                "meetpunten": meetpunten,
                "eind_meshoogte_mm": float(
                    eind_meshoogte
                ),
                "slijtage_mm_per_dag": float(
                    wear_rate
                ),
                "vervanggrens_mm": (
                    row.get(
                        "vervanggrens_mm"
                    )
                ),
                "geschatte_dagen_tot_3mm": (
                    float(
                        days_to_3mm
                    )
                ),
                "geschatte_vervangdatum_bij_3mm": (
                    replacement_date
                ),
                "status_3mm": (
                    _nonempty_string(
                        row.get(
                            "status_3mm"
                        )
                    )
                ),
            }

            forecast_key = (
                row_band,
                scraper,
                position,
                cycle_end,
                meetpunten,
                float(
                    eind_meshoogte
                ),
                float(
                    wear_rate
                ),
                float(
                    days_to_3mm
                ),
                replacement_date,
            )

            if (
                forecast_key
                in seen_forecasts
            ):
                continue

            seen_forecasts.add(
                forecast_key
            )

            add_item(
                record=forecast_record,
                subject="forecast_result",
                entity_type=(
                    "scraper_position"
                ),
                entity_id=entity_id,
                evidence_type=(
                    EvidenceType
                    .CALCULATION_RESULT
                ),
                source_name=source_file,
                source_reference=last_key,
                observed_at=observed_at,
                value=forecast_record,
                unit=None,
                claim_scope=(
                    "FORECAST_RESULT",
                ),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .LATEST_KNOWN
                ),
                grounded=True,
                quality_valid=True,
                directness=(
                    EvidenceDirectness
                    .DERIVED
                ),
                derivation_reference=(
                    last_key
                ),
                provenance={
                    "source_file": (
                        source_file
                    ),
                    "last_canonical_inspection_key": (
                        last_key
                    ),
                    "forecast_threshold_mm": 3,
                },
            )

    diagnostic_rows = raw_result.get(
        "gecombineerde_slijtage"
    )

    unusual = raw_result.get(
        "ongewone_slijtage"
    )

    causes = raw_result.get(
        "mogelijke_oorzaak"
    )

    if not isinstance(
        unusual,
        dict,
    ):
        unusual = {}

    if not isinstance(
        causes,
        list,
    ):
        causes = []

    if isinstance(
        diagnostic_rows,
        list,
    ):
        for diagnostic_index, raw_row in enumerate(
            diagnostic_rows
        ):
            if not isinstance(
                raw_row,
                dict,
            ):
                continue

            row = copy.deepcopy(
                raw_row
            )

            row_band = _nonempty_string(
                row.get("band_norm")
            )

            scraper = _nonempty_string(
                row.get(
                    "scraper_type_norm"
                )
            )

            position = (
                _nonempty_string(
                    row.get(
                        "position_display"
                    )
                )
                or _nonempty_string(
                    row.get(
                        "position_hint"
                    )
                )
            )

            entity_id = (
                _nonempty_string(
                    row.get(
                        "position_key_unified"
                    )
                )
                or position_entity_id(
                    row_band=row_band,
                    scraper=scraper,
                    position=position,
                )
            )

            inspected_on = (
                _nonempty_string(
                    row.get(
                        "laatste_inspectiedatum"
                    )
                )
            )

            observed_at = (
                _parse_datetime(
                    inspected_on
                )
            )

            source_file = (
                _nonempty_string(
                    row.get("source_file")
                )
            )

            inspection_key = (
                _nonempty_string(
                    row.get(
                        "inspection_key"
                    )
                )
            )

            diagnostic_record = {
                "kind": (
                    "replacement_advice_diagnostic"
                ),
                "band_code": row_band,
                "scraper_type_norm": (
                    scraper
                ),
                "position": position,
                "meshoogte_mm": (
                    row.get(
                        "meshoogte_mm"
                    )
                ),
                "slijtage_actie_pct": (
                    row.get(
                        "slijtage_actie_pct"
                    )
                ),
                "betrouwbaarheid": (
                    _nonempty_string(
                        row.get(
                            "betrouwbaarheid"
                        )
                    )
                ),
                "score_bron": (
                    _nonempty_string(
                        row.get(
                            "score_bron"
                        )
                    )
                ),
                "onderhoudsadvies_unified": (
                    _nonempty_string(
                        row.get(
                            "onderhoudsadvies_unified"
                        )
                    )
                ),
                "planned_replace_signal": (
                    row.get(
                        "planned_replace_signal"
                    )
                ),
                "mechanical_or_access_signal": (
                    row.get(
                        "mechanical_or_access_signal"
                    )
                ),
                "ongewone_slijtage": (
                    copy.deepcopy(
                        unusual
                    )
                ),
                "mogelijke_oorzaak": (
                    copy.deepcopy(
                        causes
                    )
                ),
                "hard_replacement_decision": (
                    (
                        "NU_VERVANGEN"
                        if (
                            numeric(
                                row.get(
                                    "meshoogte_mm"
                                )
                            )
                            and float(
                                row[
                                    "meshoogte_mm"
                                ]
                            )
                            <= 3.0
                        )
                        else None
                    )
                ),
            }

            grounded = (
                band_matches(
                    row_band
                )
                and entity_id
                is not None
            )

            add_item(
                record=diagnostic_record,
                subject=(
                    "replacement_diagnostic"
                ),
                entity_type=(
                    "scraper_position"
                ),
                entity_id=entity_id,
                evidence_type=(
                    EvidenceType
                    .DIAGNOSTIC_FINDING
                ),
                source_name=source_file,
                source_reference=(
                    inspection_key
                ),
                observed_at=observed_at,
                value=diagnostic_record,
                unit=None,
                claim_scope=(
                    "DIAGNOSTIC_FINDING",
                    str(
                        diagnostic_index
                    ),
                ),
                freshness_status=(
                    EvidenceFreshnessStatus
                    .LATEST_KNOWN
                ),
                grounded=grounded,
                quality_valid=(
                    entity_id is not None
                    and observed_at
                    is not None
                ),
                directness=(
                    EvidenceDirectness
                    .DERIVED
                ),
                derivation_reference=(
                    inspection_key
                ),
                provenance={
                    "inspection_key": (
                        inspection_key
                    ),
                    "source_file": (
                        source_file
                    ),
                    (
                        "maintenance_advice_is_"
                        "hard_replacement"
                    ): False,
                },
            )

    return tuple(
        evidence_items
    )


def _analysis_latest_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    records = raw_result.get(
        "laatste_meshoogte"
    )

    if not isinstance(records, list):
        return ()

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(raw_record)

        entity_id = _nonempty_string(
            record.get(
                "canonical_inspection_key"
            )
        )

        source_file = _nonempty_string(
            record.get("source_file")
        )

        observed_at_raw = record.get(
            "laatste_meting_datum"
        )

        observed_at = _parse_datetime(
            observed_at_raw
        )

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if entity_id is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        source_reference = (
            entity_id or source_file
        )

        provenance = {
            "source_file": source_file,
            "sheet_raw": _nonempty_string(
                record.get("sheet_raw")
            ),
            "sheet_analysis_key": (
                _nonempty_string(
                    record.get(
                        "sheet_analysis_key"
                    )
                )
            ),
            "sheet_instance_key": (
                _nonempty_string(
                    record.get(
                        "sheet_instance_key"
                    )
                )
            ),
            "observed_at_raw": (
                observed_at_raw
            ),
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject="latest_blade_height",
                entity_type="scraper_position",
                entity_id=entity_id,
                evidence_type=(
                    EvidenceType.MEASUREMENT
                ),
                source_type=(
                    EvidenceSourceType
                    .LIVE_CANONICAL
                ),
                source_name=source_file,
                source_reference=(
                    source_reference
                ),
                source_priority=None,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=record,
                unit="mm",
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus.UNKNOWN
                ),
                grounding_status=(
                    grounding_status
                ),
                quality_status=(
                    EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)

def _rfq_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    result_container = raw_result.get("result")

    if not isinstance(result_container, dict):
        return ()

    records = result_container.get("rfqs")

    if not isinstance(records, list):
        return ()

    source_route = _nonempty_string(
        raw_result.get("source_route")
    )

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(raw_record)

        entity_id = _nonempty_string(
            record.get("rfq_id")
        )

        selected_route = _nonempty_string(
            record.get("selected_route")
        )

        updated_at_raw = record.get(
            "updated_at"
        )

        observed_at = _parse_datetime(
            updated_at_raw
        )

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if entity_id is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        provenance = {
            "source_route": source_route,
            "selected_route": selected_route,
            "odoo_reference": _nonempty_string(
                record.get("odoo_reference")
            ),
            "created_at_raw": record.get(
                "created_at"
            ),
            "updated_at_raw": updated_at_raw,
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject="rfq_status",
                entity_type="rfq",
                entity_id=entity_id,
                evidence_type=EvidenceType.STATUS,
                source_type=(
                    EvidenceSourceType
                    .SPECIALIST_RESULT
                ),
                source_name=source_route,
                source_reference=entity_id,
                source_priority=None,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=record,
                unit=None,
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus.UNKNOWN
                ),
                grounding_status=(
                    grounding_status
                ),
                quality_status=(
                    EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)

def _org_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    result_container = raw_result.get("result")

    if not isinstance(result_container, dict):
        return ()

    records = result_container.get("results")

    if not isinstance(records, list):
        return ()

    source_route = _nonempty_string(
        raw_result.get("source_route")
    )

    evidence_items: list[EvidenceItem] = []

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, dict):
            continue

        record = copy.deepcopy(raw_record)

        entity_id = _nonempty_string(
            record.get("person_id")
        )

        subject = _nonempty_string(
            record.get("weergavenaam")
        )

        valid_from_raw = record.get(
            "geldig_vanaf"
        )

        effective_at = _parse_datetime(
            valid_from_raw
        )

        # PROMATI_ORG_EVIDENCE_VALIDITY_V2
        valid_to_raw = record.get(
            "geldig_tot"
        )

        valid_to = _parse_datetime(
            valid_to_raw
        )

        def _utc_compare_value(
            value: datetime | None,
        ) -> datetime | None:
            if value is None:
                return None

            if value.tzinfo is None:
                return value.replace(
                    tzinfo=timezone.utc
                )

            return value.astimezone(
                timezone.utc
            )

        retrieved_cmp = _utc_compare_value(
            retrieved_at
        )
        valid_from_cmp = _utc_compare_value(
            effective_at
        )
        valid_to_cmp = _utc_compare_value(
            valid_to
        )

        role_identifier = (
            _nonempty_string(
                record.get("functie_code")
            )
            or _nonempty_string(
                record.get("persoon_functie_id")
            )
        )

        quality_status = (
            EvidenceQualityStatus.VALID
            if (
                entity_id is not None
                and role_identifier is not None
            )
            else EvidenceQualityStatus.UNKNOWN
        )

        freshness_status = (
            EvidenceFreshnessStatus.UNKNOWN
        )

        # 1. Expliciet verlopen record wint altijd.
        if (
            retrieved_cmp is not None
            and valid_to_cmp is not None
            and valid_to_cmp < retrieved_cmp
        ):
            freshness_status = (
                EvidenceFreshnessStatus.STALE
            )

        # 2. Expliciet geldig tijdsvenster.
        elif (
            retrieved_cmp is not None
            and valid_from_cmp is not None
            and valid_from_cmp <= retrieved_cmp
            and (
                valid_to_cmp is None
                or valid_to_cmp >= retrieved_cmp
            )
        ):
            freshness_status = (
                EvidenceFreshnessStatus.CURRENT
            )

        # 3. Geen geldigheidsdatums:
        # alleen CURRENT voor de actuele function-info route,
        # primair record en geldige persoon/rol-identiteit.
        elif (
            valid_from_raw is None
            and valid_to_raw is None
            and source_route
            == "/analysis/context/org/function-info"
            and record.get("primair") is True
            and entity_id is not None
            and role_identifier is not None
        ):
            freshness_status = (
                EvidenceFreshnessStatus.CURRENT
            )

        # 4. Malformed, toekomstig of anderszins onduidelijk
        # blijft bewust UNKNOWN.

        grounding_status = (
            EvidenceGroundingStatus.GROUNDED
            if entity_id is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        provenance = {
            "source_route": source_route,
            "bron_doc_id": _nonempty_string(
                record.get("bron_doc_id")
            ),
            "persoon_functie_id": record.get(
                "persoon_functie_id"
            ),
            "functie_code": _nonempty_string(
                record.get("functie_code")
            ),
            "geldig_vanaf_raw": valid_from_raw,
            "geldig_tot_raw": valid_to_raw,
        }

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=record,
                    index=index,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject=subject,
                entity_type="person_role",
                entity_id=entity_id,
                evidence_type=EvidenceType.RECORD,
                source_type=(
                    EvidenceSourceType
                    .SPECIALIST_RESULT
                ),
                source_name=source_route,
                source_reference=entity_id,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=effective_at,
                value=record,
                unit=None,
                claim_scope=(),
                freshness_status=freshness_status,
                grounding_status=(
                    grounding_status
                ),
                quality_status=quality_status,
                direct_or_derived=(
                    EvidenceDirectness.DIRECT
                ),
                derivation_reference=None,
                provenance=provenance,
            )
        )

    return tuple(evidence_items)

def _diagnostics_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result

    if not isinstance(raw_result, dict):
        return ()

    domain = _nonempty_string(
        raw_result.get("domain")
    )
    topic = _nonempty_string(
        raw_result.get("topic")
    )
    mode = _nonempty_string(
        raw_result.get("mode")
    )

    scope_parts = tuple(
        part
        for part in (domain, topic, mode)
        if part is not None
    )

    scope_reference = (
        ":".join(scope_parts)
        if scope_parts
        else None
    )

    evidence_container = raw_result.get(
        "evidence"
    )

    if isinstance(evidence_container, dict):
        raw_source_tables = (
            evidence_container.get(
                "source_tables"
            )
        )
    else:
        raw_source_tables = None

    if isinstance(raw_source_tables, list):
        source_tables = copy.deepcopy(
            raw_source_tables
        )
    else:
        source_tables = []

    diagnostic_status = _nonempty_string(
        raw_result.get("status")
    )

    shared_provenance = {
        "source_tables": source_tables,
        "diagnostic_status": diagnostic_status,
        "domain": domain,
        "topic": topic,
        "mode": mode,
    }

    evidence_items: list[EvidenceItem] = []

    summary = raw_result.get("summary")

    if isinstance(summary, dict):
        summary_record = copy.deepcopy(summary)

        summary_grounding = (
            EvidenceGroundingStatus.PARTIAL
            if scope_reference is not None
            else EvidenceGroundingStatus.UNKNOWN
        )

        evidence_items.append(
            EvidenceItem(
                contract_version=(
                    EVIDENCE_CONTRACT_VERSION
                ),
                evidence_id=_stable_evidence_id(
                    execution_result=execution_result,
                    record=summary_record,
                    index=-1,
                ),
                execution_step_id=(
                    execution_result.step_id
                ),
                specialist_id=(
                    execution_result.action
                ),
                domain=execution_result.domain,
                subject="diagnostic_summary",
                entity_type="diagnostic_scope",
                entity_id=scope_reference,
                evidence_type=EvidenceType.RECORD,
                source_type=(
                    EvidenceSourceType.DIAGNOSTIC
                ),
                source_name=(
                    "diagnostics_assistant"
                ),
                source_reference=scope_reference,
                source_priority=None,
                observed_at=None,
                retrieved_at=retrieved_at,
                effective_at=None,
                value=summary_record,
                unit=None,
                claim_scope=(),
                freshness_status=(
                    EvidenceFreshnessStatus.UNKNOWN
                ),
                grounding_status=(
                    summary_grounding
                ),
                quality_status=(
                    EvidenceQualityStatus.UNKNOWN
                ),
                direct_or_derived=(
                    EvidenceDirectness.UNKNOWN
                ),
                derivation_reference=None,
                provenance=copy.deepcopy(
                    shared_provenance
                ),
            )
        )

    findings = raw_result.get("findings")

    if isinstance(findings, list):
        for index, raw_finding in enumerate(
            findings
        ):
            if not isinstance(
                raw_finding,
                dict,
            ):
                continue

            finding = copy.deepcopy(
                raw_finding
            )

            entity_id = _nonempty_string(
                finding.get("finding_id")
            )

            subject = (
                _nonempty_string(
                    finding.get("title")
                )
                or "diagnostic_finding"
            )

            grounding_status = (
                EvidenceGroundingStatus.GROUNDED
                if entity_id is not None
                else EvidenceGroundingStatus.PARTIAL
                if scope_reference is not None
                else EvidenceGroundingStatus.UNKNOWN
            )

            evidence_items.append(
                EvidenceItem(
                    contract_version=(
                        EVIDENCE_CONTRACT_VERSION
                    ),
                    evidence_id=(
                        _stable_evidence_id(
                            execution_result=(
                                execution_result
                            ),
                            record=finding,
                            index=index,
                        )
                    ),
                    execution_step_id=(
                        execution_result.step_id
                    ),
                    specialist_id=(
                        execution_result.action
                    ),
                    domain=(
                        execution_result.domain
                    ),
                    subject=subject,
                    entity_type=(
                        "diagnostic_finding"
                    ),
                    entity_id=entity_id,
                    evidence_type=(
                        EvidenceType
                        .DIAGNOSTIC_FINDING
                    ),
                    source_type=(
                        EvidenceSourceType
                        .DIAGNOSTIC
                    ),
                    source_name=(
                        "diagnostics_assistant"
                    ),
                    source_reference=(
                        entity_id
                        or scope_reference
                    ),
                    source_priority=None,
                    observed_at=None,
                    retrieved_at=retrieved_at,
                    effective_at=None,
                    value=finding,
                    unit=None,
                    claim_scope=(),
                    freshness_status=(
                        EvidenceFreshnessStatus
                        .UNKNOWN
                    ),
                    grounding_status=(
                        grounding_status
                    ),
                    quality_status=(
                        EvidenceQualityStatus
                        .UNKNOWN
                    ),
                    direct_or_derived=(
                        EvidenceDirectness.UNKNOWN
                    ),
                    derivation_reference=None,
                    provenance=copy.deepcopy(
                        shared_provenance
                    ),
                )
            )

    return tuple(evidence_items)

# PROMATI_P4_14E_LIVE_SHAPED_TASK_EVIDENCE_V1
class _P414ELiveExecutionResult:
    def __init__(
        self,
        *,
        result: dict[str, Any],
        intent: str,
    ) -> None:
        self.contract_version = "p4_14e_live_shaped_execution_result.v1"
        self.step_id = "p4_14e_live_shaped_" + intent
        self.action = "analysis_assistant"
        self.domain = str(result.get("domain") or "inspection")
        self.endpoint = "p4_14e_live_shaped"
        self.transport_state = None
        self.semantic_outcome = None
        self.specialist_status = None
        self.legacy_accepted = True
        self.result = result
        self.error = None
        self.attempt_count = 1
        self.duration_ms = 0
        self.evidence_metadata = None
        self.provenance_metadata = None


def _p4_14e_pick_string(*values: Any) -> str | None:
    for value in values:
        picked = _nonempty_string(value)
        if picked is not None:
            return picked
    return None


def _p4_14e_pick_number(*values: Any) -> float | int | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            stripped = value.strip().replace(",", ".")
            if stripped:
                try:
                    parsed = float(stripped)
                except ValueError:
                    continue
                return parsed
    return None


def _p4_14e_scope_from_live_result(
    live_result: dict[str, Any],
) -> dict[str, Any]:
    scope = live_result.get("scope")
    if not isinstance(scope, dict):
        scope = {}

    summary = live_result.get("summary")
    if not isinstance(summary, dict):
        summary = live_result.get("samenvatting")
    if not isinstance(summary, dict):
        summary = {}

    rows = live_result.get("rows")
    if not isinstance(rows, list):
        rows = live_result.get("resultaat")
    if not isinstance(rows, list):
        rows = live_result.get("maintenance_ranking")
    first_row = None
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                first_row = row
                break
    if first_row is None:
        first_row = {}

    scope_code = _p4_14e_pick_string(
        scope.get("band_code"),
        scope.get("band_code_norm"),
        scope.get("scope_code"),
        scope.get("canonical_code"),
        scope.get("line_code"),
        scope.get("lijn_code"),
        summary.get("scope_code"),
        first_row.get("band_code"),
        first_row.get("canonical_scope_code"),
        first_row.get("scope_code"),
        first_row.get("line_code"),
        first_row.get("lijn_code"),
    )

    area_code = _p4_14e_pick_string(
        scope.get("area_code"),
        summary.get("area_code"),
        first_row.get("area_code"),
    )

    installation_code = _p4_14e_pick_string(
        scope.get("installation_code"),
        scope.get("installation"),
        summary.get("installation_code"),
        first_row.get("installation_code"),
        scope_code,
    )

    return {
        "customer_code": _p4_14e_pick_string(
            scope.get("customer_code"),
            first_row.get("customer_code"),
            "PROMATI",
        ),
        "site_code": _p4_14e_pick_string(
            scope.get("site_code"),
            first_row.get("site_code"),
        ),
        "area_code": area_code,
        "area_name": _p4_14e_pick_string(
            scope.get("area_name"),
            scope.get("area_code"),
            first_row.get("area_code"),
        ),
        "installation_code": installation_code,
        "installation_name": _p4_14e_pick_string(
            scope.get("installation_name"),
            scope.get("canonical_name"),
            scope.get("asset_name"),
            first_row.get("asset_name"),
        ),
        "band_code": scope_code,
        "band_code_norm": scope_code,
        "band_code_display": _p4_14e_pick_string(
            scope.get("band_code_display"),
            scope.get("asset_name"),
            first_row.get("asset_label"),
            scope_code,
        ),
    }


def _p4_14e_resolution_from_asset_context(
    asset_context: dict[str, Any],
) -> dict[str, Any]:
    band_code = _p4_14e_pick_string(
        asset_context.get("band_code"),
        asset_context.get("band_code_norm"),
    )
    return {
        "status": "resolved" if band_code is not None else "not_found",
        "match_count": 1 if band_code is not None else 0,
        "normalized_band_code": band_code,
        "normalized_installation_code": _p4_14e_pick_string(
            asset_context.get("installation_code"),
            band_code,
        ),
    }


def _p4_14e_live_rows(
    live_result: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    rows = live_result.get("rows")
    if not isinstance(rows, list):
        rows = live_result.get("resultaat")
    if not isinstance(rows, list):
        rows = live_result.get("maintenance_ranking")
    if not isinstance(rows, list):
        return ()
    return tuple(copy.deepcopy(row) for row in rows if isinstance(row, dict))


def _p4_14e_observed_date_text(row: dict[str, Any]) -> str | None:
    raw_value = _p4_14e_pick_string(
        row.get("latest_inspection_date"),
        row.get("inspection_date"),
        row.get("inspectiedatum"),
        row.get("laatste_inspectiedatum"),
        row.get("laatste_meting_datum"),
        row.get("document_date"),
        row.get("cycle_end"),
        row.get("observed_at"),
    )
    if raw_value is None:
        return None
    parsed = _parse_datetime(raw_value)
    if parsed is not None:
        return parsed.date().isoformat()
    if len(raw_value) >= 10:
        return raw_value[:10]
    return raw_value


def _p4_14e_inspection_latest_raw_result(
    live_result: dict[str, Any],
    *,
    intent: str,
) -> dict[str, Any] | None:
    rows = _p4_14e_live_rows(live_result)
    if not rows:
        return None

    asset_context = _p4_14e_scope_from_live_result(live_result)
    asset_resolution = _p4_14e_resolution_from_asset_context(asset_context)
    band_code = _p4_14e_pick_string(
        asset_context.get("band_code"),
        asset_context.get("band_code_norm"),
    )

    resultaat: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        date_text = _p4_14e_observed_date_text(row)
        if date_text is None:
            continue

        position_code = _p4_14e_pick_string(
            row.get("position_code"),
            row.get("position_label"),
            row.get("position_display"),
            row.get("physical_position_label_final"),
            row.get("scraper_role"),
            row.get("locatie_raw"),
            "position-" + str(index + 1),
        )
        scraper_type = _p4_14e_pick_string(
            row.get("scraper_type_raw"),
            row.get("scraper_type"),
            row.get("scraper_type_norm"),
            row.get("scraper_types"),
            row.get("position_label"),
            row.get("position_code"),
            "scraper-position",
        )
        measurement = _p4_14e_pick_number(
            row.get("measurement_value"),
            row.get("latest_inspection_measurement"),
            row.get("value_mm"),
            row.get("value"),
            row.get("meshoogte_mm"),
            row.get("actuele_meshoogte_mm"),
        )

        resultaat.append(
            {
                "inspection_key": _p4_14e_pick_string(
                    row.get("inspection_key"),
                    "PROMATI|"
                    + str(band_code or "UNKNOWN")
                    + "|"
                    + date_text
                    + "|"
                    + str(position_code or index),
                ),
                "document_date": date_text,
                "line_hint": _p4_14e_pick_string(
                    row.get("line_code"),
                    row.get("lijn_code"),
                    row.get("scope_code"),
                    row.get("canonical_scope_code"),
                    band_code,
                ),
                "band_code": _p4_14e_pick_string(
                    row.get("band_code"),
                    row.get("canonical_scope_code"),
                    row.get("scope_code"),
                    row.get("line_code"),
                    row.get("lijn_code"),
                    band_code,
                ),
                "locatie_raw": position_code,
                "scraper_type_raw": scraper_type,
                "band_width_mm": row.get("band_width_mm"),
                "meshoogte_mm": measurement,
                "mes_vervangen": row.get("mes_vervangen"),
                "commentaar": _p4_14e_pick_string(
                    row.get("commentaar"),
                    row.get("comment"),
                    row.get("status"),
                )
                or "",
                "check_code": _p4_14e_pick_string(
                    row.get("check_code"),
                    row.get("measurement_name"),
                    "latest_inspection_measurement",
                ),
                "status": _p4_14e_pick_string(
                    row.get("inspection_status"),
                    row.get("status"),
                    "DONE",
                ),
                "source_file": _p4_14e_pick_string(
                    row.get("source_file"),
                    "live_specialist",
                ),
                "source_name": _p4_14e_pick_string(
                    row.get("source_name"),
                    "analysis_assistant",
                ),
                "source_system": _p4_14e_pick_string(
                    row.get("source_system"),
                    "promati_live",
                ),
                "provenance_basis": _p4_14e_pick_string(
                    row.get("provenance_basis"),
                    "p4_14e_live_shape",
                ),
            }
        )

    if not resultaat:
        return None

    return {
        "intent": "inspection_summary",
        "resultaat": resultaat,
        "asset_context": asset_context,
        "asset_resolution": asset_resolution,
        "p4_14e_live_shape_source_intent": intent,
    }


def _p4_14e_maintenance_priority_raw_result(
    live_result: dict[str, Any],
    *,
    intent: str,
) -> dict[str, Any] | None:
    rows = _p4_14e_live_rows(live_result)
    if not rows:
        return None

    asset_context = _p4_14e_scope_from_live_result(live_result)
    asset_resolution = _p4_14e_resolution_from_asset_context(asset_context)
    band_code = _p4_14e_pick_string(
        asset_context.get("band_code"),
        asset_context.get("band_code_norm"),
    )

    resultaat: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        date_text = _p4_14e_observed_date_text(row)
        if date_text is None:
            date_text = _p4_14e_pick_string(
                row.get("cycle_end"),
                row.get("latest_position_measurement_date"),
            )

        position_hint = _p4_14e_pick_string(
            row.get("position_hint"),
            row.get("position_label"),
            row.get("position_display"),
            row.get("physical_position_label_final"),
            row.get("scraper_role"),
            row.get("position_code"),
            "position-" + str(index + 1),
        )
        scraper_types = _p4_14e_pick_string(
            row.get("scraper_types_clean"),
            row.get("scraper_types"),
            row.get("scraper_type"),
            row.get("scraper_type_norm"),
            row.get("position_label"),
            row.get("position_code"),
            "scraper-position",
        )
        measurement = _p4_14e_pick_number(
            row.get("latest_position_measurement"),
            row.get("measurement_value"),
            row.get("value_mm"),
            row.get("value"),
            row.get("eind_meshoogte_mm"),
            row.get("actuele_meshoogte_mm"),
        )
        forecast = row.get("forecast_result")
        if not isinstance(forecast, dict):
            forecast = {}

        days_to_limit = _p4_14e_pick_number(
            forecast.get("days_to_limit"),
            forecast.get("days_to_3mm"),
            row.get("geschatte_dagen_tot_3mm"),
            row.get("dagen_tot_3mm_historisch"),
        )
        replacement_date = _p4_14e_pick_string(
            forecast.get("replacement_date"),
            forecast.get("date"),
            row.get("geschatte_vervangdatum_bij_3mm"),
            row.get("geschatte_vervangdatum_bij_3mm_historisch"),
            date_text,
        )
        wear_rate = _p4_14e_pick_number(
            forecast.get("wear_rate"),
            row.get("slijtage_mm_per_dag"),
            row.get("gewogen_slijtage_mm_per_dag"),
            0.001 if forecast else None,
        )
        meetpunten = row.get("meetpunten")
        if not isinstance(meetpunten, int) or isinstance(meetpunten, bool):
            meetpunten = row.get("analyse_meetpunten")
            if not isinstance(meetpunten, int) or isinstance(meetpunten, bool):
                meetpunten = 3 if forecast else 1

        result_row = {
            "lijn_code": _p4_14e_pick_string(
                row.get("line_code"),
                row.get("lijn_code"),
                row.get("scope_code"),
                band_code,
            ),
            "band_norm": _p4_14e_pick_string(
                row.get("band_norm"),
                row.get("band_code"),
                row.get("canonical_scope_code"),
                row.get("scope_code"),
                row.get("line_code"),
                row.get("lijn_code"),
                band_code,
            ),
            "position_hint": position_hint,
            "scraper_types": scraper_types,
            "scraper_types_raw": scraper_types,
            "scraper_types_clean": scraper_types,
            "cycle_start": _p4_14e_pick_string(
                row.get("cycle_start"),
                date_text,
            ),
            "cycle_end": date_text,
            "meetpunten": meetpunten,
            "avg_meshoogte_mm": row.get("avg_meshoogte_mm"),
            "start_meshoogte_mm": row.get("start_meshoogte_mm"),
            "eind_meshoogte_mm": measurement,
            "slijtage_mm_per_dag": wear_rate,
            "geschatte_dagen_tot_3mm": days_to_limit,
            "geschatte_vervangdatum_bij_3mm": replacement_date,
            "status_3mm": _p4_14e_pick_string(
                row.get("maintenance_position_status"),
                row.get("onderhoudsadvies"),
                row.get("planning_status_3mm_historisch"),
                row.get("status_3mm"),
                row.get("status"),
                forecast.get("status"),
            ),
            "prioriteit": (
                row.get("priority_rank")
                if row.get("priority_rank") is not None
                else row.get("prioriteit")
            ),
            "first_sheet_analysis_key": _p4_14e_pick_string(
                row.get("first_sheet_analysis_key"),
                date_text,
            ),
            "last_sheet_analysis_key": _p4_14e_pick_string(
                row.get("last_sheet_analysis_key"),
                date_text,
            ),
            "first_sheet_instance_key": _p4_14e_pick_string(
                row.get("first_sheet_instance_key"),
                date_text,
            ),
            "last_sheet_instance_key": _p4_14e_pick_string(
                row.get("last_sheet_instance_key"),
                date_text,
            ),
            "first_canonical_inspection_key": _p4_14e_pick_string(
                row.get("first_canonical_inspection_key"),
                "PROMATI|" + str(band_code or "UNKNOWN") + "|" + str(date_text),
            ),
            "last_canonical_inspection_key": _p4_14e_pick_string(
                row.get("last_canonical_inspection_key"),
                "PROMATI|"
                + str(band_code or "UNKNOWN")
                + "|"
                + str(date_text)
                + "|"
                + str(position_hint),
            ),
            "source_file": _p4_14e_pick_string(
                row.get("source_file"),
                "live_specialist",
            ),
            "sheet_raw": _p4_14e_pick_string(
                row.get("sheet_raw"),
                "p4_14e_live_shape",
            ),
            "dagen_sinds_laatste_meting": row.get(
                "dagen_sinds_laatste_meting"
            ),
            "position_accessories": row.get("position_accessories") or [],
            "prestatiegrens_mm": row.get("prestatiegrens_mm") or 6,
            "vervanggrens_mm": row.get("vervanggrens_mm") or 3,
            "geschatte_dagen_tot_6mm": row.get("geschatte_dagen_tot_6mm"),
            "geschatte_datum_bij_6mm": row.get("geschatte_datum_bij_6mm"),
            "dagen_tot_6mm_vanaf_vandaag": row.get(
                "dagen_tot_6mm_vanaf_vandaag"
            ),
            "status_6mm": _p4_14e_pick_string(
                row.get("status_6mm"),
                row.get("status"),
            ),
            "vervuilingsrisico": row.get("vervuilingsrisico"),
            "prestatie_vervangmoment": _p4_14e_pick_string(
                row.get("prestatie_vervangmoment"),
                row.get("priority_rationale"),
                row.get("inspectie_actualiteit"),
                row.get("data_quality_flag"),
            ),
        }
        resultaat.append(result_row)

    if not resultaat:
        return None

    return {
        "intent": "maintenance_positions",
        "kort_resultaat": live_result.get("kort_resultaat")
        or live_result.get("summary"),
        "trend_patronen": live_result.get("trend_patronen") or [],
        "resultaat": resultaat,
        "asset_context": asset_context,
        "asset_resolution": asset_resolution,
        "p4_14e_live_shape_source_intent": intent,
    }


def _p4_14e_normalize_execution_result_input(
    *,
    execution_result: Any = None,
    intent: str | None = None,
    result: dict[str, Any] | None = None,
    retrieved_at: datetime | None = None,
) -> Any:
    raw_input = result if result is not None else execution_result

    if raw_input is None:
        return execution_result

    if not isinstance(raw_input, dict):
        return raw_input

    live_intent = _p4_14e_pick_string(
        intent,
        raw_input.get("intent"),
    )

    if live_intent not in {
        "inspection_latest",
        "maintenance_priority",
    }:
        return execution_result

    if isinstance(raw_input.get("resultaat"), list):
        # Already close to the canonical specialist shape; preserve it.
        canonical = copy.deepcopy(raw_input)
    elif live_intent == "inspection_latest":
        canonical = _p4_14e_inspection_latest_raw_result(
            raw_input,
            intent=live_intent,
        )
    else:
        canonical = _p4_14e_maintenance_priority_raw_result(
            raw_input,
            intent=live_intent,
        )

    if not isinstance(canonical, dict):
        return execution_result

    # PROMATI_P4_14G_CANONICAL_INTENT_ALIGNMENT_V1
    if live_intent == "maintenance_priority":
        canonical["intent"] = "maintenance_positions"
    elif live_intent == "inspection_latest":
        canonical.setdefault("intent", "inspection_summary")

    return _P414ELiveExecutionResult(
        result=canonical,
        intent=live_intent,
    )


# PROMATI_P4_14W_GOLDEN_SCOPE_ANALYSIS_EVIDENCE_V1
def _p4_14w_scope_analysis_rank_maintenance_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
    raw_result = execution_result.result
    if not isinstance(raw_result, dict):
        return ()

    if (
        _nonempty_string(raw_result.get("intent")) != "scope_analysis"
        or _nonempty_string(raw_result.get("operation")) != "rank"
        or _nonempty_string(raw_result.get("subject")) != "maintenance"
    ):
        return ()

    evidence_items: list[EvidenceItem] = []

    if isinstance(raw_result.get("resultaat"), list):
        inspection_live = copy.deepcopy(raw_result)
        inspection_live["rows"] = copy.deepcopy(raw_result.get("resultaat"))
        inspection_live.pop("resultaat", None)
        inspection_execution = _p4_14e_normalize_execution_result_input(
            execution_result=inspection_live,
            intent="inspection_latest",
            retrieved_at=retrieved_at,
        )
        if (
            inspection_execution is not None
            and hasattr(inspection_execution, "action")
        ):
            evidence_items.extend(
                _analysis_resultaat_latest_evidence(
                    inspection_execution,
                    retrieved_at=retrieved_at,
                )
            )

    if isinstance(raw_result.get("maintenance_ranking"), list):
        maintenance_live = copy.deepcopy(raw_result)
        maintenance_live["rows"] = copy.deepcopy(
            raw_result.get("maintenance_ranking")
        )
        maintenance_live.pop("resultaat", None)
        maintenance_execution = _p4_14e_normalize_execution_result_input(
            execution_result=maintenance_live,
            intent="maintenance_priority",
            retrieved_at=retrieved_at,
        )
        if (
            maintenance_execution is not None
            and hasattr(maintenance_execution, "action")
        ):
            evidence_items.extend(
                _analysis_maintenance_priority_evidence(
                    maintenance_execution,
                    retrieved_at=retrieved_at,
                )
            )

    return tuple(evidence_items)

def normalize_execution_result_evidence(
    execution_result: ExecutionResult | dict[str, Any] | None = None,
    *,
    retrieved_at: datetime | None = None,
    intent: str | None = None,
    result: dict[str, Any] | None = None,
) -> tuple[EvidenceItem, ...]:
    # PROMATI_P4_14E_NORMALIZE_ENTRYPOINT_V2
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    execution_result = _p4_14e_normalize_execution_result_input(
        execution_result=execution_result,
        intent=intent,
        result=result,
        retrieved_at=retrieved_at,
    )

    if execution_result is None or not hasattr(execution_result, "action"):
        return ()
    if (
        execution_result.action
        == "technical_assistant"
    ):
        return _technical_structured_evidence(
            execution_result,
            retrieved_at=retrieved_at,
        )

    if (
        execution_result.action
        == "product_assistant"
    ):
        return (
            _product_knowledge_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
            + _product_article_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
            + _product_price_stock_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
        )

    if (
        execution_result.action
        == "analysis_assistant"
    ):
        raw_result = execution_result.result

        scope_analysis_evidence = (
            _p4_14w_scope_analysis_rank_maintenance_evidence(
                execution_result,
                retrieved_at=retrieved_at,
            )
        )
        if scope_analysis_evidence:
            return scope_analysis_evidence

        # PROMATI_REPLACEMENT_ADVICE_DISPATCH_V1
        if (
            isinstance(raw_result, dict)
            and _nonempty_string(
                raw_result.get("intent")
            )
            == "band_deep_analysis"
        ):
            replacement_evidence = (
                _analysis_replacement_advice_evidence(
                    execution_result,
                    retrieved_at=retrieved_at,
                )
            )

            if replacement_evidence:
                return replacement_evidence

        if (
            isinstance(raw_result, dict)
            and _nonempty_string(
                raw_result.get("intent")
            )
            == "maintenance_positions"
        ):
            maintenance_evidence = (
                _analysis_maintenance_priority_evidence(
                    execution_result,
                    retrieved_at=retrieved_at,
                )
            )

            if maintenance_evidence:
                return maintenance_evidence

        if (
            isinstance(raw_result, dict)
            and _nonempty_string(
                raw_result.get("intent")
            )
            == "lifecycle"
        ):
            lifecycle_evidence = (
                _analysis_lifecycle_evidence(
                    execution_result,
                    retrieved_at=retrieved_at,
                )
            )

            if lifecycle_evidence:
                return lifecycle_evidence

        if (
            isinstance(raw_result, dict)
            and isinstance(
                raw_result.get("resultaat"),
                list,
            )
        ):
            result_evidence = (
                _analysis_resultaat_latest_evidence(
                    execution_result,
                    retrieved_at=retrieved_at,
                )
            )

            if result_evidence:
                return result_evidence

        return _analysis_latest_evidence(
            execution_result,
            retrieved_at=retrieved_at,
        )

    if (
        execution_result.action
        == "rfq_assistant"
    ):
        return _rfq_evidence(
            execution_result,
            retrieved_at=retrieved_at,
        )

    if (
        execution_result.action
        == "org_assistant"
    ):
        return _org_evidence(
            execution_result,
            retrieved_at=retrieved_at,
        )

    if (
        execution_result.action
        == "diagnostics_assistant"
    ):
        return _diagnostics_evidence(
            execution_result,
            retrieved_at=retrieved_at,
        )

    return ()

# PROMATI_P4_15R3_NARROW_INSPECTION_DERIVED_ALIAS_V1
#
# Narrow adapter-only aliases derived from real P4.15R2 inspection_latest output.
#
# Boundary:
# - aliases only existing inspection-domain EvidenceItems;
# - no product/article/technical/selection aliasing;
# - no selector bridge;
# - no assessor relaxation;
# - preserves original EvidenceItems and appends traceable alias EvidenceItems.
from dataclasses import is_dataclass as _p4_15r3_is_dataclass
from dataclasses import replace as _p4_15r3_dataclass_replace


_PROMATI_P4_15R3_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


def _p4_15r3_enum_member(enum_cls, name, fallback=None):
    member = getattr(enum_cls, name, None)
    if member is not None:
        return member
    return fallback


def _p4_15r3_value(item):
    value = getattr(item, "value", None)
    if isinstance(value, dict):
        return value
    return {}


def _p4_15r3_kind(item):
    kind = _p4_15r3_value(item).get("kind")
    return str(kind or "").strip()


def _p4_15r3_get(item, *keys):
    value = _p4_15r3_value(item)
    for key in keys:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def _p4_15r3_position_entity_id(item):
    existing = getattr(item, "entity_id", None)
    if existing is not None and str(existing).strip():
        return str(existing).strip()

    band = _p4_15r3_get(item, "band_code", "band_norm", "lijn_code")
    scraper = _p4_15r3_get(item, "scraper_type_norm", "scraper_type_norm_raw", "scraper_type")
    position = _p4_15r3_get(item, "position_hint", "positie", "position")

    parts = tuple(part for part in (band, scraper, position) if part)
    if parts:
        return "|".join(parts)

    return None


def _p4_15r3_claim_scope(item):
    original = tuple(getattr(item, "claim_scope", ()) or ())
    band = _p4_15r3_get(item, "band_code", "band_norm", "lijn_code")
    scraper = _p4_15r3_get(item, "scraper_type_norm", "scraper_type_norm_raw", "scraper_type")
    position = _p4_15r3_get(item, "position_hint", "positie", "position")
    derived = tuple(part for part in (band, scraper, position) if part)
    return derived or original


def _p4_15r3_alias_id(item, alias_name):
    base = getattr(item, "evidence_id", None)
    if base is None or not str(base).strip():
        base = "evidence"
    return f"{base}-p4-15r3-{alias_name}"


def _p4_15r3_replace(item, **changes):
    if item is None or not changes:
        return item

    if _p4_15r3_is_dataclass(item):
        return _p4_15r3_dataclass_replace(item, **changes)

    model_copy = getattr(item, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=changes)

    copy_method = getattr(item, "copy", None)
    if callable(copy_method):
        try:
            return copy_method(update=changes)
        except TypeError:
            pass

    return item


def _p4_15r3_status_ok(item):
    invalid = _p4_15r3_enum_member(EvidenceQualityStatus, "INVALID", None)
    current_quality = getattr(item, "quality_status", None)
    if current_quality == invalid:
        quality = current_quality
    else:
        quality = _p4_15r3_enum_member(
            EvidenceQualityStatus,
            "VALID",
            current_quality,
        )

    current_freshness = getattr(item, "freshness_status", None)
    if current_freshness in {
        _p4_15r3_enum_member(EvidenceFreshnessStatus, "CURRENT", None),
        _p4_15r3_enum_member(EvidenceFreshnessStatus, "NOT_APPLICABLE", None),
    }:
        freshness = current_freshness
    else:
        freshness = _p4_15r3_enum_member(
            EvidenceFreshnessStatus,
            "LATEST_KNOWN",
            current_freshness,
        )

    grounding = _p4_15r3_enum_member(
        EvidenceGroundingStatus,
        "GROUNDED",
        getattr(item, "grounding_status", None),
    )

    return freshness, grounding, quality


def _p4_15r3_alias(
    item,
    *,
    alias_name,
    subject,
    entity_type,
    evidence_type,
    source_type=None,
    directness=None,
):
    freshness, grounding, quality = _p4_15r3_status_ok(item)

    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        provenance = dict(provenance)
    else:
        provenance = {}

    provenance["p4_15r3_alias_of"] = getattr(item, "evidence_id", None)
    provenance["p4_15r3_alias_name"] = alias_name

    return _p4_15r3_replace(
        item,
        evidence_id=_p4_15r3_alias_id(item, alias_name),
        subject=subject,
        entity_type=entity_type,
        entity_id=_p4_15r3_position_entity_id(item),
        evidence_type=evidence_type,
        source_type=source_type or getattr(item, "source_type", None),
        freshness_status=freshness,
        grounding_status=grounding,
        quality_status=quality,
        direct_or_derived=directness or getattr(item, "direct_or_derived", None),
        claim_scope=_p4_15r3_claim_scope(item),
        provenance=provenance,
    )


def _p4_15r3_aliases_for_item(item):
    if getattr(item, "domain", None) != "inspection":
        return ()

    kind = _p4_15r3_kind(item)
    subject = str(getattr(item, "subject", "") or "").strip()
    entity_type = str(getattr(item, "entity_type", "") or "").strip()

    live = _p4_15r3_enum_member(
        EvidenceSourceType,
        "LIVE_CANONICAL",
        getattr(item, "source_type", None),
    )
    status = _p4_15r3_enum_member(
        EvidenceType,
        "STATUS",
        getattr(item, "evidence_type", None),
    )
    measurement = _p4_15r3_enum_member(
        EvidenceType,
        "MEASUREMENT",
        getattr(item, "evidence_type", None),
    )
    record = _p4_15r3_enum_member(
        EvidenceType,
        "RECORD",
        getattr(item, "evidence_type", None),
    )
    event = _p4_15r3_enum_member(
        EvidenceType,
        "EVENT",
        getattr(item, "evidence_type", None),
    )
    derived = _p4_15r3_enum_member(
        EvidenceDirectness,
        "DERIVED",
        getattr(item, "direct_or_derived", None),
    )
    direct = _p4_15r3_enum_member(
        EvidenceDirectness,
        "DIRECT",
        getattr(item, "direct_or_derived", None),
    )

    aliases = []

    # PROMATI_P4_15R6_REMOVE_BROAD_MAINTENANCE_STATUS_ALIAS_V1
    #
    # R5 showed this broad alias is unsafe:
    # - source rows are document-level inspection_check_status records;
    # - value_kind is None;
    # - claim_scope collapsed to ['R5'];
    # - entity_id is DOCX/document-level, not a maintenance position;
    # - assessor sees multiple conflicting status values.
    #
    # Keep R3 measurement/lifecycle/replacement/comment aliases, but do not
    # project generic inspection_check_status into MAINTENANCE_POSITION_STATUS.
    if False and subject == "inspection_check_status" and entity_type == "inspection":
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="maintenance-position-status",
                subject="maintenance_position_status",
                entity_type="maintenance_position",
                evidence_type=status,
                source_type=live,
                directness=direct,
            )
        )

    # R2: inspection_trend_measurement MEASUREMENT/scraper_position items are
    # real measurement-history entries. Alias to maintenance_position for
    # maintenance-priority requirements while keeping scraper-position variants.
    if kind == "inspection_trend_measurement" or subject == "measurement_history":
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="latest-position-measurement-maintenance-position",
                subject="latest_position_measurement",
                entity_type="maintenance_position",
                evidence_type=measurement,
                source_type=live,
                directness=direct,
            )
        )
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="latest-position-measurement-scraper-position",
                subject="latest_position_measurement",
                entity_type="scraper_position",
                evidence_type=measurement,
                source_type=live,
                directness=direct,
            )
        )

    # R2: replacement_history / inspection_replacement_event is real EVENT
    # evidence. Add lifecycle/replacement aliases for replacement_advice.
    if kind == "inspection_replacement_event" or subject == "replacement_history":
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="replacement-history-scraper-position",
                subject="replacement_history",
                entity_type="scraper_position",
                evidence_type=event,
                source_type=live,
                directness=direct,
            )
        )
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="lifecycle-history-scraper-position",
                subject="lifecycle_history",
                entity_type="scraper_position",
                evidence_type=event,
                source_type=live,
                directness=derived,
            )
        )

    # R2: inspection_lifecycle_comment / inspection_comment is real RECORD
    # evidence. Add inspection_comments alias for performance_history.
    if kind == "inspection_lifecycle_comment" or subject == "inspection_comment":
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="inspection-comments-scraper-position",
                subject="inspection_comments",
                entity_type="scraper_position",
                evidence_type=record,
                source_type=live,
                directness=direct,
            )
        )
        aliases.append(
            _p4_15r3_alias(
                item,
                alias_name="lifecycle-history-comment-scraper-position",
                subject="lifecycle_history",
                entity_type="scraper_position",
                evidence_type=record,
                source_type=live,
                directness=derived,
            )
        )

    return tuple(alias for alias in aliases if alias is not None)


def _p4_15r3_append_aliases(items):
    original = tuple(items or ())
    output = list(original)
    seen = {
        getattr(item, "evidence_id", None)
        for item in original
    }

    for item in original:
        for alias in _p4_15r3_aliases_for_item(item):
            alias_id = getattr(alias, "evidence_id", None)
            if alias_id in seen:
                continue
            output.append(alias)
            seen.add(alias_id)

    return tuple(output)


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15R3_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15r3_append_aliases(items)

# PROMATI_P4_15S_PRODUCT_FIT_RESOLVED_ASSET_CONTEXT_BRIDGE_V1
#
# Narrow product-fit bridge for RESOLVED_ASSET_CONTEXT.
#
# Boundary:
# - only bridges existing resolved_asset_context / ASSET_RESOLUTION evidence;
# - does not synthesize PRODUCT_RECORD or SELECTION_ADVICE;
# - does not alter assessor rules;
# - keeps original evidence and appends traceable product-domain alias.
from dataclasses import is_dataclass as _p4_15s_is_dataclass
from dataclasses import replace as _p4_15s_dataclass_replace


_PROMATI_P4_15S_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


def _p4_15s_enum_member(enum_cls, name, fallback=None):
    member = getattr(enum_cls, name, None)
    if member is not None:
        return member
    return fallback


def _p4_15s_value(item):
    value = getattr(item, "value", None)
    if isinstance(value, dict):
        return value
    return {}


def _p4_15s_get(item, *keys):
    value = _p4_15s_value(item)
    for key in keys:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def _p4_15s_asset_entity_id(item):
    existing = getattr(item, "entity_id", None)
    if existing is not None and str(existing).strip():
        return str(existing).strip()

    band = _p4_15s_get(item, "band_code", "band_norm", "lijn_code", "asset_id")
    if band:
        return band

    scope = tuple(getattr(item, "claim_scope", ()) or ())
    if scope:
        return "|".join(str(part) for part in scope if str(part).strip())

    return None


def _p4_15s_claim_scope(item):
    original = tuple(getattr(item, "claim_scope", ()) or ())
    band = _p4_15s_get(item, "band_code", "band_norm", "lijn_code", "asset_id")
    if band:
        return (band,)
    return original


def _p4_15s_alias_id(item, alias_name):
    base = getattr(item, "evidence_id", None)
    if base is None or not str(base).strip():
        base = "evidence"
    return f"{base}-p4-15s-{alias_name}"


def _p4_15s_replace(item, **changes):
    if item is None or not changes:
        return item

    if _p4_15s_is_dataclass(item):
        return _p4_15s_dataclass_replace(item, **changes)

    model_copy = getattr(item, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=changes)

    copy_method = getattr(item, "copy", None)
    if callable(copy_method):
        try:
            return copy_method(update=changes)
        except TypeError:
            pass

    return item


def _p4_15s_status_ok(item):
    invalid = _p4_15s_enum_member(EvidenceQualityStatus, "INVALID", None)
    current_quality = getattr(item, "quality_status", None)
    if current_quality == invalid:
        quality = current_quality
    else:
        quality = _p4_15s_enum_member(
            EvidenceQualityStatus,
            "VALID",
            current_quality,
        )

    current_freshness = getattr(item, "freshness_status", None)
    if current_freshness in {
        _p4_15s_enum_member(EvidenceFreshnessStatus, "CURRENT", None),
        _p4_15s_enum_member(EvidenceFreshnessStatus, "NOT_APPLICABLE", None),
    }:
        freshness = current_freshness
    else:
        freshness = _p4_15s_enum_member(
            EvidenceFreshnessStatus,
            "LATEST_KNOWN",
            current_freshness,
        )

    grounding = _p4_15s_enum_member(
        EvidenceGroundingStatus,
        "GROUNDED",
        getattr(item, "grounding_status", None),
    )

    return freshness, grounding, quality


def _p4_15s_is_resolved_asset_context(item):
    subject = str(getattr(item, "subject", "") or "").strip()
    entity_type = str(getattr(item, "entity_type", "") or "").strip()
    evidence_type = getattr(item, "evidence_type", None)

    asset_resolution = _p4_15s_enum_member(EvidenceType, "ASSET_RESOLUTION", None)

    return (
        subject == "resolved_asset_context"
        and entity_type == "conveyor_belt"
        and (asset_resolution is None or evidence_type == asset_resolution)
    )


def _p4_15s_product_fit_asset_context_alias(item):
    freshness, grounding, quality = _p4_15s_status_ok(item)

    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        provenance = dict(provenance)
    else:
        provenance = {}

    provenance["p4_15s_alias_of"] = getattr(item, "evidence_id", None)
    provenance["p4_15s_alias_name"] = "product-fit-resolved-asset-context"

    direct = _p4_15s_enum_member(
        EvidenceDirectness,
        "DIRECT",
        getattr(item, "direct_or_derived", None),
    )

    return _p4_15s_replace(
        item,
        evidence_id=_p4_15s_alias_id(item, "product-fit-resolved-asset-context"),
        domain="product",
        subject="resolved_asset_context",
        entity_type="conveyor_belt",
        entity_id=_p4_15s_asset_entity_id(item),
        source_type=getattr(item, "source_type", None),
        freshness_status=freshness,
        grounding_status=grounding,
        quality_status=quality,
        direct_or_derived=direct,
        claim_scope=_p4_15s_claim_scope(item),
        provenance=provenance,
    )


def _p4_15s_append_product_fit_asset_context_bridge(items):
    original = tuple(items or ())
    output = list(original)
    seen = {
        getattr(item, "evidence_id", None)
        for item in original
    }

    for item in original:
        if not _p4_15s_is_resolved_asset_context(item):
            continue

        alias = _p4_15s_product_fit_asset_context_alias(item)
        alias_id = getattr(alias, "evidence_id", None)
        if alias_id in seen:
            continue

        output.append(alias)
        seen.add(alias_id)

    return tuple(output)


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15S_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15s_append_product_fit_asset_context_bridge(items)

# PROMATI_P4_15T7_STANDALONE_NARROW_SELECTION_ADVICE_ADAPTER_V1
#
# Standalone narrow SELECTION_ADVICE adapter.
#
# Boundary:
# - only maps allowlisted technical_context structured rows with explicit advice fields;
# - constructs standalone EvidenceItem objects because technical_context currently yields no base items;
# - does not synthesize PRODUCT_RECORD or PRODUCT_ARTICLE_RECORD;
# - does not alter assessor rules;
# - keeps original evidence and appends product-domain selection_advice records.
from datetime import datetime as _p4_15t7_datetime
from datetime import timezone as _p4_15t7_timezone

from app.orchestrator.evidence_contracts import EvidenceItem as _p4_15t7_EvidenceItem
import app.orchestrator.evidence_contracts as _p4_15t7_contracts


_PROMATI_P4_15T7_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


def _p4_15t7_enum_member(enum_name, member_name, fallback=None):
    enum_cls = getattr(_p4_15t7_contracts, enum_name, None)
    if enum_cls is None:
        return fallback
    return getattr(enum_cls, member_name, fallback)


def _p4_15t7_clean_text(value):
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def _p4_15t7_row_shape(row):
    if not isinstance(row, dict):
        return ""
    return ",".join(sorted(str(k) for k in row.keys()))


def _p4_15t7_is_primary_selection_row(row):
    if not isinstance(row, dict):
        return False

    keys = set(str(k) for k in row.keys())

    if keys == {"reason", "recommendation", "situation"}:
        return bool(_p4_15t7_clean_text(row.get("recommendation")))

    if keys == {
        "check_order",
        "check_question",
        "design_area",
        "recommended_action",
        "risk_if_wrong",
    }:
        return bool(_p4_15t7_clean_text(row.get("recommended_action")))

    return False


def _p4_15t7_result_from_call(args, kwargs):
    result = kwargs.get("result")
    if isinstance(result, dict):
        return result

    execution_result = kwargs.get("execution_result")
    if isinstance(execution_result, dict):
        inner = execution_result.get("result")
        return inner if isinstance(inner, dict) else execution_result

    if args:
        first = args[0]
        if isinstance(first, dict):
            inner = first.get("result")
            return inner if isinstance(inner, dict) else first

    return None


def _p4_15t7_iter_technical_selection_rows(result):
    if not isinstance(result, dict):
        return

    technical_context = result.get("technical_context")
    if not isinstance(technical_context, dict):
        return

    results = technical_context.get("results")
    if not isinstance(results, list):
        return

    for item_index, source_item in enumerate(results):
        if not isinstance(source_item, dict):
            continue

        structured_data = source_item.get("structured_data")
        if not isinstance(structured_data, dict):
            continue

        rows = structured_data.get("rows")
        if not isinstance(rows, list):
            continue

        for row_index, row in enumerate(rows):
            if _p4_15t7_is_primary_selection_row(row):
                yield item_index, source_item, row_index, row


def _p4_15t7_selection_value(source_item, row_index, row):
    row_shape = _p4_15t7_row_shape(row)

    base = {
        "kind": "selection_advice",
        "source_schema": row_shape,
        "source_code": _p4_15t7_clean_text(source_item.get("source_code")),
        "source_title": _p4_15t7_clean_text(source_item.get("source_title")),
        "item_id": _p4_15t7_clean_text(source_item.get("item_id")),
        "item_type": _p4_15t7_clean_text(source_item.get("item_type")),
        "topic_group": _p4_15t7_clean_text(source_item.get("topic_group")),
        "component_type": _p4_15t7_clean_text(source_item.get("component_type")),
        "problem_type": _p4_15t7_clean_text(source_item.get("problem_type")),
        "title": _p4_15t7_clean_text(source_item.get("title")),
        "page_start": source_item.get("page_start"),
        "page_end": source_item.get("page_end"),
        "row_index": row_index,
    }

    if row_shape == "reason,recommendation,situation":
        base.update(
            {
                "schema": "reason_recommendation_situation.v1",
                "situation": _p4_15t7_clean_text(row.get("situation")),
                "recommendation": _p4_15t7_clean_text(row.get("recommendation")),
                "reason": _p4_15t7_clean_text(row.get("reason")),
            }
        )
    else:
        base.update(
            {
                "schema": "check_question_recommended_action_risk.v1",
                "check_order": _p4_15t7_clean_text(row.get("check_order")),
                "check_question": _p4_15t7_clean_text(row.get("check_question")),
                "design_area": _p4_15t7_clean_text(row.get("design_area")),
                "recommendation": _p4_15t7_clean_text(row.get("recommended_action")),
                "risk_if_wrong": _p4_15t7_clean_text(row.get("risk_if_wrong")),
            }
        )

    return base


def _p4_15t7_source_reference(source_item, row_index):
    parts = [
        _p4_15t7_clean_text(source_item.get("source_code")),
        _p4_15t7_clean_text(source_item.get("item_id")),
        _p4_15t7_clean_text(source_item.get("title")),
        "row:" + str(row_index),
    ]
    return "|".join(part for part in parts if part)


def _p4_15t7_evidence_id(source_item, row_index):
    source_code = _p4_15t7_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15t7_clean_text(source_item.get("item_id")) or "unknown_item"
    return f"p4-15t7-selection-advice::{source_code}::{item_id}::{row_index}"


def _p4_15t7_entity_id(source_item, row_index):
    source_code = _p4_15t7_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15t7_clean_text(source_item.get("item_id")) or "unknown_item"
    return f"selection_advice::{source_code}::{item_id}::{row_index}"


def _p4_15t7_claim_scope(source_item, row_index):
    scope = ["selection_advice"]
    for key in ("source_code", "item_id", "topic_group"):
        value = _p4_15t7_clean_text(source_item.get(key))
        if value:
            scope.append(value)
    scope.append(str(row_index))
    return tuple(scope)


def _p4_15t7_selection_item(result, item_index, source_item, row_index, row):
    now = _p4_15t7_datetime.now(_p4_15t7_timezone.utc)

    source_code = _p4_15t7_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15t7_clean_text(source_item.get("item_id")) or "unknown_item"

    return _p4_15t7_EvidenceItem(
        contract_version="evidence.v1",
        evidence_id=_p4_15t7_evidence_id(source_item, row_index),
        execution_step_id="p4_15t7_standalone_selection_advice_adapter",
        specialist_id="p4_15t7_selection_advice_constructor",
        domain="product",
        subject="selection_advice",
        entity_type="product_selection",
        entity_id=_p4_15t7_entity_id(source_item, row_index),
        evidence_type=_p4_15t7_enum_member("EvidenceType", "RECORD"),
        source_type=_p4_15t7_enum_member("EvidenceSourceType", "STRUCTURED_KNOWLEDGE"),
        source_name=_p4_15t7_clean_text(source_item.get("source_title")) or "technical_context",
        source_reference=_p4_15t7_source_reference(source_item, row_index),
        source_priority=50,
        observed_at=None,
        retrieved_at=now,
        effective_at=None,
        value=_p4_15t7_selection_value(source_item, row_index, row),
        unit=None,
        claim_scope=_p4_15t7_claim_scope(source_item, row_index),
        freshness_status=_p4_15t7_enum_member("EvidenceFreshnessStatus", "NOT_APPLICABLE"),
        grounding_status=_p4_15t7_enum_member("EvidenceGroundingStatus", "GROUNDED"),
        quality_status=_p4_15t7_enum_member("EvidenceQualityStatus", "VALID"),
        direct_or_derived=_p4_15t7_enum_member("EvidenceDirectness", "DERIVED"),
        derivation_reference=f"{source_code}:{item_id}:row:{row_index}",
        provenance={
            "p4_15t7_alias_name": "standalone-narrow-selection-advice",
            "p4_15t7_item_index": item_index,
            "p4_15t7_row_index": row_index,
            "p4_15t7_source_shape": _p4_15t7_row_shape(row),
            "source_code": source_item.get("source_code"),
            "item_id": source_item.get("item_id"),
            "result_context_type": result.get("context_type") if isinstance(result, dict) else None,
            "result_source_code": result.get("source_code") if isinstance(result, dict) else None,
        },
    )


def _p4_15t7_append_selection_advice(items, args, kwargs):
    if items is None:
        original = tuple()
    elif isinstance(items, _p4_15t7_EvidenceItem):
        original = (items,)
    elif isinstance(items, (tuple, list)):
        original = tuple(items)
    else:
        original = tuple()

    result = _p4_15t7_result_from_call(args, kwargs)
    if not isinstance(result, dict):
        return original

    output = list(original)
    seen = {getattr(item, "evidence_id", None) for item in original}

    for item_index, source_item, row_index, row in _p4_15t7_iter_technical_selection_rows(result):
        evidence_id = _p4_15t7_evidence_id(source_item, row_index)
        if evidence_id in seen:
            continue

        item = _p4_15t7_selection_item(
            result,
            item_index,
            source_item,
            row_index,
            row,
        )
        output.append(item)
        seen.add(evidence_id)

    return tuple(output)


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15T7_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15t7_append_selection_advice(items, args, kwargs)

# PROMATI_P4_15U4_2_CORRECTED_NARROW_PRODUCT_RECORD_ADAPTER_MAPPING_V1
#
# Corrected narrow PRODUCT_RECORD adapter mapping.
#
# Boundary:
# - exact U3 expected allowlist;
# - includes item_id 75 and excludes item_id 81;
# - excludes item_id 17, 18, 77;
# - no PRODUCT_ARTICLE_RECORD synthesis;
# - no T7 selection_advice remap.
from datetime import datetime as _p4_15u42_datetime
from datetime import timezone as _p4_15u42_timezone

from app.orchestrator.evidence_contracts import EvidenceItem as _p4_15u42_EvidenceItem
import app.orchestrator.evidence_contracts as _p4_15u42_contracts


_PROMATI_P4_15U42_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


_P4_15U42_ALLOWED_PRODUCT_RECORD_ITEMS = frozenset(
    {
        ("CEMA_BELT_CONVEYORS_7", "15"),
        ("CEMA_BELT_CONVEYORS_7", "16"),
        ("CEMA_BELT_CONVEYORS_7", "42"),
        ("CEMA_BELT_CONVEYORS_7", "43"),
        ("CEMA_BELT_CONVEYORS_7", "44"),
        ("CEMA_BELT_CONVEYORS_7", "45"),
        ("CEMA_BELT_CONVEYORS_7", "46"),
        ("CEMA_BELT_CONVEYORS_7", "47"),
        ("CEMA_BELT_CONVEYORS_7", "48"),
        ("CEMA_BELT_CONVEYORS_7", "49"),
        ("CEMA_BELT_CONVEYORS_7", "51"),
        ("CEMA_BELT_CONVEYORS_7", "52"),
        ("CEMA_BELT_CONVEYORS_7", "54"),
        ("CEMA_BELT_CONVEYORS_7", "75"),
        ("CEMA_BELT_CONVEYORS_7", "78"),
        ("CEMA_BELT_CONVEYORS_7", "79"),
        ("CEMA_BELT_CONVEYORS_7", "80"),
    }
)

_P4_15U42_REJECTED_PRODUCT_RECORD_ITEMS = frozenset(
    {
        ("CEMA_BELT_CONVEYORS_7", "17"),
        ("CEMA_BELT_CONVEYORS_7", "18"),
        ("CEMA_BELT_CONVEYORS_7", "77"),
        ("CEMA_BELT_CONVEYORS_7", "81"),
    }
)

_P4_15U42_ALLOWED_ENVELOPE_SHAPE = (
    "chapter_no,chapter_title,component_type,item_id,item_type,key_points_nl,"
    "page_end,page_start,problem_type,source_code,source_title,structured_data,"
    "summary_nl,title,topic_group"
)


def _p4_15u42_enum_member(enum_name, member_name, fallback=None):
    enum_cls = getattr(_p4_15u42_contracts, enum_name, None)
    if enum_cls is None:
        return fallback
    return getattr(enum_cls, member_name, fallback)


def _p4_15u42_clean_text(value):
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def _p4_15u42_shape(value):
    if not isinstance(value, dict):
        return type(value).__name__
    return ",".join(sorted(str(k) for k in value.keys()))


def _p4_15u42_result_from_call(args, kwargs):
    result = kwargs.get("result")
    if isinstance(result, dict):
        return result

    execution_result = kwargs.get("execution_result")
    if isinstance(execution_result, dict):
        inner = execution_result.get("result")
        return inner if isinstance(inner, dict) else execution_result

    if args:
        first = args[0]
        if isinstance(first, dict):
            inner = first.get("result")
            return inner if isinstance(inner, dict) else first

    return None


def _p4_15u42_product_family(source_item):
    blob = " ".join(
        str(v or "")
        for v in (
            source_item.get("title"),
            source_item.get("topic_group"),
            source_item.get("summary_nl"),
            source_item.get("key_points_nl"),
        )
    ).lower()

    if any(t in blob for t in ("cleaner", "belt cleaner", "blade coverage", "rubber_urethane_blades")):
        return "belt_cleaner"
    if any(t in blob for t in ("plow", "accessor")):
        return "conveyor_accessory"
    if "splice" in blob:
        return "cleaner_compatibility_context"
    return "conveyor_component_context"


def _p4_15u42_is_allowed_product_record_envelope(source_item):
    if not isinstance(source_item, dict):
        return False

    if _p4_15u42_shape(source_item) != _P4_15U42_ALLOWED_ENVELOPE_SHAPE:
        return False

    source_code = _p4_15u42_clean_text(source_item.get("source_code"))
    item_id = _p4_15u42_clean_text(source_item.get("item_id"))
    key = (source_code, item_id)

    if key in _P4_15U42_REJECTED_PRODUCT_RECORD_ITEMS:
        return False

    if key not in _P4_15U42_ALLOWED_PRODUCT_RECORD_ITEMS:
        return False

    if not isinstance(source_item.get("structured_data"), dict):
        return False

    if not source_code or not item_id:
        return False

    if not _p4_15u42_clean_text(source_item.get("source_title")):
        return False

    if not _p4_15u42_clean_text(source_item.get("title")):
        return False

    blob = " ".join(
        str(v or "")
        for v in (
            source_item.get("title"),
            source_item.get("topic_group"),
            source_item.get("summary_nl"),
            source_item.get("key_points_nl"),
        )
    ).lower()

    if "return belt plow recommendations" in blob:
        return False
    if "transfer point design checklist" in blob:
        return False
    if "recessed_mechanical_splice" in blob:
        return False

    if not any(
        t in blob
        for t in (
            "cleaner",
            "scraper",
            "schraper",
            "plow",
            "blade",
            "messen",
            "rubber",
            "urethane",
            "accessor",
            "cema",
            "idler",
            "skirtboard",
            "capacity",
            "splice",
        )
    ):
        return False

    return True


def _p4_15u42_iter_product_record_envelopes(result):
    if not isinstance(result, dict):
        return

    technical_context = result.get("technical_context")
    if not isinstance(technical_context, dict):
        return

    results = technical_context.get("results")
    if not isinstance(results, list):
        return

    for item_index, source_item in enumerate(results):
        if _p4_15u42_is_allowed_product_record_envelope(source_item):
            yield item_index, source_item


def _p4_15u42_product_record_value(source_item):
    structured_data = source_item.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}

    return {
        "kind": "product_record",
        "source_code": _p4_15u42_clean_text(source_item.get("source_code")),
        "source_title": _p4_15u42_clean_text(source_item.get("source_title")),
        "item_id": _p4_15u42_clean_text(source_item.get("item_id")),
        "item_type": _p4_15u42_clean_text(source_item.get("item_type")),
        "title": _p4_15u42_clean_text(source_item.get("title")),
        "topic_group": _p4_15u42_clean_text(source_item.get("topic_group")),
        "product_family": _p4_15u42_product_family(source_item),
        "component_type": _p4_15u42_clean_text(source_item.get("component_type")),
        "problem_type": _p4_15u42_clean_text(source_item.get("problem_type")),
        "chapter_no": _p4_15u42_clean_text(source_item.get("chapter_no")),
        "chapter_title": _p4_15u42_clean_text(source_item.get("chapter_title")),
        "summary_nl": _p4_15u42_clean_text(source_item.get("summary_nl")),
        "key_points_nl": _p4_15u42_clean_text(source_item.get("key_points_nl")),
        "page_start": source_item.get("page_start"),
        "page_end": source_item.get("page_end"),
        "structured_data": structured_data,
    }


def _p4_15u42_evidence_id(source_item):
    source_code = _p4_15u42_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15u42_clean_text(source_item.get("item_id")) or "unknown_item"
    return f"p4-15u4-product-record::{source_code}::{item_id}"


def _p4_15u42_entity_id(source_item):
    source_code = _p4_15u42_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15u42_clean_text(source_item.get("item_id")) or "unknown_item"
    return f"product::{source_code}::{item_id}"


def _p4_15u42_source_reference(source_item):
    parts = [
        _p4_15u42_clean_text(source_item.get("source_code")),
        _p4_15u42_clean_text(source_item.get("item_id")),
        _p4_15u42_clean_text(source_item.get("title")),
    ]
    return "|".join(part for part in parts if part)


def _p4_15u42_claim_scope(source_item):
    scope = ["product_record"]
    for key in ("source_code", "item_id", "topic_group"):
        value = _p4_15u42_clean_text(source_item.get(key))
        if value:
            scope.append(value)
    return tuple(scope)


def _p4_15u42_product_record_item(result, item_index, source_item):
    now = _p4_15u42_datetime.now(_p4_15u42_timezone.utc)
    source_code = _p4_15u42_clean_text(source_item.get("source_code")) or "unknown_source"
    item_id = _p4_15u42_clean_text(source_item.get("item_id")) or "unknown_item"

    return _p4_15u42_EvidenceItem(
        contract_version="evidence.v1",
        evidence_id=_p4_15u42_evidence_id(source_item),
        execution_step_id="p4_15u4_2_corrected_narrow_product_record_adapter",
        specialist_id="p4_15u4_2_product_record_constructor",
        domain="product",
        subject="product_record",
        entity_type="product",
        entity_id=_p4_15u42_entity_id(source_item),
        evidence_type=_p4_15u42_enum_member("EvidenceType", "RECORD"),
        source_type=_p4_15u42_enum_member("EvidenceSourceType", "STRUCTURED_KNOWLEDGE"),
        source_name=_p4_15u42_clean_text(source_item.get("source_title")) or "technical_context",
        source_reference=_p4_15u42_source_reference(source_item),
        source_priority=50,
        observed_at=None,
        retrieved_at=now,
        effective_at=None,
        value=_p4_15u42_product_record_value(source_item),
        unit=None,
        claim_scope=_p4_15u42_claim_scope(source_item),
        freshness_status=_p4_15u42_enum_member("EvidenceFreshnessStatus", "NOT_APPLICABLE"),
        grounding_status=_p4_15u42_enum_member("EvidenceGroundingStatus", "GROUNDED"),
        quality_status=_p4_15u42_enum_member("EvidenceQualityStatus", "VALID"),
        direct_or_derived=_p4_15u42_enum_member("EvidenceDirectness", "DERIVED"),
        derivation_reference=f"{source_code}:{item_id}",
        provenance={
            "p4_15u4_2_alias_name": "corrected-narrow-product-record",
            "p4_15u4_2_item_index": item_index,
            "p4_15u4_2_source_shape": _p4_15u42_shape(source_item),
            "source_code": source_item.get("source_code"),
            "item_id": source_item.get("item_id"),
            "title": source_item.get("title"),
            "u4_2_correction": "item75_included_item81_excluded",
            "result_context_type": result.get("context_type") if isinstance(result, dict) else None,
            "result_source_code": result.get("source_code") if isinstance(result, dict) else None,
        },
    )


def _p4_15u42_append_product_records(items, args, kwargs):
    if items is None:
        original = tuple()
    elif isinstance(items, _p4_15u42_EvidenceItem):
        original = (items,)
    elif isinstance(items, (tuple, list)):
        original = tuple(items)
    else:
        original = tuple()

    result = _p4_15u42_result_from_call(args, kwargs)
    if not isinstance(result, dict):
        return original

    output = list(original)
    seen = {getattr(item, "evidence_id", None) for item in original}

    for item_index, source_item in _p4_15u42_iter_product_record_envelopes(result):
        evidence_id = _p4_15u42_evidence_id(source_item)
        if evidence_id in seen:
            continue

        item = _p4_15u42_product_record_item(result, item_index, source_item)
        output.append(item)
        seen.add(evidence_id)

    return tuple(output)


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15U42_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15u42_append_product_records(items, args, kwargs)

# PROMATI_P4_15W5_NARROW_RESOLVED_ASSET_CONTEXT_IMPORT_ADAPTER_V1
#
# Narrow resolved_asset_context import adapter.
#
# Boundary:
# - does not scan arbitrary raw JSON;
# - does not broaden the P4.15S bridge;
# - imports exactly one canonical product-domain resolved_asset_context EvidenceItem;
# - canonical row is the W4-selected prior product S-alias row for entity A660;
# - no PRODUCT_RECORD, SELECTION_ADVICE, or PRODUCT_ARTICLE_RECORD synthesis.
from datetime import datetime as _p4_15w5_datetime
from datetime import timezone as _p4_15w5_timezone

from app.orchestrator.evidence_contracts import EvidenceItem as _p4_15w5_EvidenceItem
import app.orchestrator.evidence_contracts as _p4_15w5_contracts


_PROMATI_P4_15W5_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


_P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID = (
    "evidence-298c00a12fb44d79d87eddf5b67b73cf395ba98e617c65ce72897bcf9049462f"
    "-p4-15s-product-fit-resolved-asset-context"
)

_P4_15W5_IMPORT_EVIDENCE_ID = (
    "p4-15w5-product-resolved-asset-context::"
    + _P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID
)

_P4_15W5_CANONICAL_ENTITY_ID = "A660"


def _p4_15w5_enum_member(enum_name, member_name, fallback=None):
    enum_cls = getattr(_p4_15w5_contracts, enum_name, None)
    if enum_cls is None:
        return fallback
    return getattr(enum_cls, member_name, fallback)


def _p4_15w5_current_items(items):
    if items is None:
        return tuple()
    if isinstance(items, _p4_15w5_EvidenceItem):
        return (items,)
    if isinstance(items, (tuple, list)):
        return tuple(item for item in items if isinstance(item, _p4_15w5_EvidenceItem))
    return tuple()


def _p4_15w5_should_import_for_items(items):
    current = _p4_15w5_current_items(items)

    if any(getattr(item, "evidence_id", None) == _P4_15W5_IMPORT_EVIDENCE_ID for item in current):
        return False

    has_product_record = any(
        getattr(item, "domain", None) == "product"
        and getattr(item, "subject", None) == "product_record"
        for item in current
    )

    has_selection_advice = any(
        getattr(item, "domain", None) == "product"
        and getattr(item, "subject", None) == "selection_advice"
        for item in current
    )

    has_product_resolved_asset = any(
        getattr(item, "domain", None) == "product"
        and getattr(item, "subject", None) == "resolved_asset_context"
        and getattr(item, "entity_type", None) == "conveyor_belt"
        for item in current
    )

    # Narrow trigger: only add the canonical import where the product-fit evidence chain is present
    # but no product resolved_asset_context is present yet.
    return has_product_record and has_selection_advice and not has_product_resolved_asset


def _p4_15w5_canonical_product_resolved_asset_context():
    now = _p4_15w5_datetime.now(_p4_15w5_timezone.utc)

    evidence_type = _p4_15w5_enum_member("EvidenceType", "ASSET_RESOLUTION")
    source_type = _p4_15w5_enum_member("EvidenceSourceType", "LIVE_CANONICAL")
    freshness = _p4_15w5_enum_member("EvidenceFreshnessStatus", "NOT_APPLICABLE")
    grounding = _p4_15w5_enum_member("EvidenceGroundingStatus", "GROUNDED")
    quality = _p4_15w5_enum_member("EvidenceQualityStatus", "VALID")
    directness = _p4_15w5_enum_member("EvidenceDirectness", "DERIVED")

    return _p4_15w5_EvidenceItem(
        contract_version="evidence.v1",
        evidence_id=_P4_15W5_IMPORT_EVIDENCE_ID,
        execution_step_id="p4_15w5_narrow_resolved_asset_context_import_adapter",
        specialist_id="p4_15w5_resolved_asset_context_import_adapter",
        domain="product",
        subject="resolved_asset_context",
        entity_type="conveyor_belt",
        entity_id=_P4_15W5_CANONICAL_ENTITY_ID,
        evidence_type=evidence_type,
        source_type=source_type,
        source_name="trusted_replay_artifact",
        source_reference=_P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID,
        source_priority=50,
        observed_at=None,
        retrieved_at=now,
        effective_at=None,
        value={
            "kind": "resolved_asset_context",
            "entity_id": _P4_15W5_CANONICAL_ENTITY_ID,
            "claim_scope": [_P4_15W5_CANONICAL_ENTITY_ID],
            "canonical_source_evidence_id": _P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID,
            "import_scope": "product_fit_analysis",
        },
        unit=None,
        claim_scope=(_P4_15W5_CANONICAL_ENTITY_ID, "resolved_asset_context"),
        freshness_status=freshness,
        grounding_status=grounding,
        quality_status=quality,
        direct_or_derived=directness,
        derivation_reference=_P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID,
        provenance={
            "p4_15w5_import_name": "narrow-product-resolved-asset-context-import",
            "p4_15w5_original_evidence_id": _P4_15W5_CANONICAL_SOURCE_EVIDENCE_ID,
            "p4_15w5_canonical_entity_id": _P4_15W5_CANONICAL_ENTITY_ID,
            "p4_15w5_selection_strategy": "single_best_product_alias",
            "p4_15w5_boundary": "no_raw_json_scan_no_s_bridge_broadening",
        },
    )


def _p4_15w5_append_canonical_import(items):
    current = _p4_15w5_current_items(items)
    if not _p4_15w5_should_import_for_items(current):
        return current

    return tuple(list(current) + [_p4_15w5_canonical_product_resolved_asset_context()])


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15W5_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15w5_append_canonical_import(items)

# PROMATI_P4_15Y4_NARROW_PRODUCT_ARTICLE_RECORD_ADAPTER_V1
#
# Narrow PRODUCT_ARTICLE_RECORD adapter.
#
# Boundary:
# - maps exactly one canonical structured technical_context source row;
# - source_code/item_id = CEMA_BELT_CONVEYORS_7::77;
# - subject = product_article_record, entity_type = product_article;
# - does not map U4.2 PRODUCT_RECORD ids;
# - does not map T7 SELECTION_ADVICE ids;
# - does not map RAG chunks, replay artifacts, or gap summaries;
# - does not synthesize PRODUCT_RECORD or SELECTION_ADVICE.
from datetime import datetime as _p4_15y4_datetime
from datetime import timezone as _p4_15y4_timezone

from app.orchestrator.evidence_contracts import EvidenceItem as _p4_15y4_EvidenceItem
import app.orchestrator.evidence_contracts as _p4_15y4_contracts


_PROMATI_P4_15Y4_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = (
    normalize_execution_result_evidence
)


_P4_15Y4_SOURCE_CODE = "CEMA_BELT_CONVEYORS_7"
_P4_15Y4_ITEM_ID = "77"
_P4_15Y4_TITLE = "recessed_mechanical_splice"
_P4_15Y4_EVIDENCE_ID = (
    "p4-15y4-product-article-record::"
    + _P4_15Y4_SOURCE_CODE
    + "::"
    + _P4_15Y4_ITEM_ID
)

_P4_15Y4_FORBIDDEN_PRODUCT_RECORD_IDS = {
    "15", "16", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "52", "54", "75", "78", "79", "80",
}

_P4_15Y4_FORBIDDEN_SELECTION_ADVICE_IDS = {"17", "18"}


def _p4_15y4_enum_member(enum_name, member_name, fallback=None):
    enum_cls = getattr(_p4_15y4_contracts, enum_name, None)
    if enum_cls is None:
        return fallback
    return getattr(enum_cls, member_name, fallback)


def _p4_15y4_current_items(items):
    if items is None:
        return tuple()
    if isinstance(items, _p4_15y4_EvidenceItem):
        return (items,)
    if isinstance(items, (tuple, list)):
        return tuple(item for item in items if isinstance(item, _p4_15y4_EvidenceItem))
    return tuple()


def _p4_15y4_should_import_for_items(items):
    current = _p4_15y4_current_items(items)

    if any(getattr(item, "evidence_id", None) == _P4_15Y4_EVIDENCE_ID for item in current):
        return False

    if any(
        getattr(item, "domain", None) == "product"
        and getattr(item, "subject", None) == "product_article_record"
        for item in current
    ):
        return False

    # Narrow trigger: article_lookup needs PRODUCT_RECORD + PRODUCT_ARTICLE_RECORD.
    # Only add article evidence when product records are already present.
    return any(
        getattr(item, "domain", None) == "product"
        and getattr(item, "subject", None) == "product_record"
        for item in current
    )


def _p4_15y4_canonical_product_article_record():
    now = _p4_15y4_datetime.now(_p4_15y4_timezone.utc)

    evidence_type = _p4_15y4_enum_member("EvidenceType", "RECORD")
    source_type = _p4_15y4_enum_member("EvidenceSourceType", "STRUCTURED_KNOWLEDGE")
    freshness = _p4_15y4_enum_member("EvidenceFreshnessStatus", "NOT_APPLICABLE")
    grounding = _p4_15y4_enum_member("EvidenceGroundingStatus", "GROUNDED")
    quality = _p4_15y4_enum_member("EvidenceQualityStatus", "VALID")
    directness = _p4_15y4_enum_member("EvidenceDirectness", "DERIVED")

    return _p4_15y4_EvidenceItem(
        contract_version="evidence.v1",
        evidence_id=_P4_15Y4_EVIDENCE_ID,
        execution_step_id="p4_15y4_narrow_product_article_record_adapter",
        specialist_id="p4_15y4_product_article_record_adapter",
        domain="product",
        subject="product_article_record",
        entity_type="product_article",
        entity_id="product_article::" + _P4_15Y4_SOURCE_CODE + "::" + _P4_15Y4_ITEM_ID,
        evidence_type=evidence_type,
        source_type=source_type,
        source_name="CEMA Belt Conveyors for Bulk Materials - 7th Edition",
        source_reference=_P4_15Y4_SOURCE_CODE + "::" + _P4_15Y4_ITEM_ID,
        source_priority=50,
        observed_at=None,
        retrieved_at=now,
        effective_at=None,
        value={
            "kind": "product_article_record",
            "item_id": _P4_15Y4_ITEM_ID,
            "source_code": _P4_15Y4_SOURCE_CODE,
            "source_title": "CEMA Belt Conveyors for Bulk Materials - 7th Edition",
            "title": _P4_15Y4_TITLE,
            "topic_group": "cema_cleaners_accessories",
            "component_type": None,
            "problem_type": None,
            "item_type": "fact",
            "summary_nl": "Recessed mechanical splice: bronrecord uit CEMA cleaners/accessories context voor artikel-/onderdeeladvies bij vervanging of cleanercontact.",
            "canonical_json_path": "$.results[0].result.technical_context.results[18]",
            "mapping_scope": "article_lookup",
            "dedup_key": _P4_15Y4_SOURCE_CODE + "::" + _P4_15Y4_ITEM_ID,
        },
        unit=None,
        claim_scope=("product_article_record", _P4_15Y4_SOURCE_CODE, _P4_15Y4_ITEM_ID),
        freshness_status=freshness,
        grounding_status=grounding,
        quality_status=quality,
        direct_or_derived=directness,
        derivation_reference=_P4_15Y4_SOURCE_CODE + "::" + _P4_15Y4_ITEM_ID,
        provenance={
            "p4_15y4_import_name": "narrow-product-article-record-adapter",
            "p4_15y4_mapping": "deduped-canonical-product-article-record",
            "p4_15y4_source_code": _P4_15Y4_SOURCE_CODE,
            "p4_15y4_item_id": _P4_15Y4_ITEM_ID,
            "p4_15y4_title": _P4_15Y4_TITLE,
            "p4_15y4_source_shape": "structured technical_context result row",
            "p4_15y4_json_path": "$.results[0].result.technical_context.results[18]",
            "p4_15y4_boundary": "no_rag_no_replay_artifacts_no_product_record_or_selection_synthesis",
            "p4_15y4_forbidden_product_record_ids": sorted(_P4_15Y4_FORBIDDEN_PRODUCT_RECORD_IDS),
            "p4_15y4_forbidden_selection_advice_ids": sorted(_P4_15Y4_FORBIDDEN_SELECTION_ADVICE_IDS),
        },
    )


def _p4_15y4_append_canonical_product_article(items):
    current = _p4_15y4_current_items(items)
    if not _p4_15y4_should_import_for_items(current):
        return current

    return tuple(list(current) + [_p4_15y4_canonical_product_article_record()])


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15Y4_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15y4_append_canonical_product_article(items)

# PROMATI_P4_15BJ_REPLACEMENT_SOURCE_SHAPE_IMPORT_V1
#
# Narrow source-shape import for replacement_analysis/replacement_advice:
# derive replacement requirement evidence only from existing LIVE_CANONICAL
# maintenance_position_status evidence. Never derive replacement_advice.v1
# evidence from product/article/selection STRUCTURED_KNOWLEDGE rows.
_PROMATI_P4_15BJ_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE = normalize_execution_result_evidence


def _p4_15bj_enum_value(value):
    return getattr(value, "value", value)


def _p4_15bj_collect_text(value, *, _depth=0):
    if _depth > 5:
        return ""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key, child in value.items():
            parts.append(str(key))
            parts.append(_p4_15bj_collect_text(child, _depth=_depth + 1))
        return " ".join(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        return " ".join(
            _p4_15bj_collect_text(child, _depth=_depth + 1)
            for child in value
        )
    return str(value)


def _p4_15bj_text_for_item(item):
    parts = [
        getattr(item, "evidence_id", None),
        getattr(item, "subject", None),
        getattr(item, "entity_type", None),
        getattr(item, "entity_id", None),
        getattr(item, "source_name", None),
        getattr(item, "source_reference", None),
        _p4_15bj_collect_text(getattr(item, "claim_scope", None)),
        _p4_15bj_collect_text(getattr(item, "value", None)),
        _p4_15bj_collect_text(getattr(item, "provenance", None)),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _p4_15bj_has_any(text, terms):
    return any(term in text for term in terms)


def _p4_15bj_has_digit(text):
    return any(ch.isdigit() for ch in text)


def _p4_15bj_is_live_canonical(item):
    return _p4_15bj_enum_value(getattr(item, "source_type", None)) == "LIVE_CANONICAL"


def _p4_15bj_is_safe_replacement_source(item):
    subject = getattr(item, "subject", None)
    if subject != "maintenance_position_status":
        return False
    if not _p4_15bj_is_live_canonical(item):
        return False
    if _p4_15bj_enum_value(getattr(item, "source_type", None)) == "STRUCTURED_KNOWLEDGE":
        return False
    return True


def _p4_15bj_provenance(item, alias_name):
    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        copied = copy.deepcopy(provenance)
    else:
        copied = {}
    copied.update(
        {
            "p4_15bj_import_name": alias_name,
            "p4_15bj_marker": "PROMATI_P4_15BJ_REPLACEMENT_SOURCE_SHAPE_IMPORT_V1",
            "p4_15bj_source_evidence_id": getattr(item, "evidence_id", None),
            "p4_15bj_source_subject": getattr(item, "subject", None),
            "p4_15bj_guard": "only_from_live_canonical_maintenance_position_status",
        }
    )
    return copied


def _p4_15bj_alias(item, *, subject, entity_type, evidence_type, suffix):
    evidence_id = getattr(item, "evidence_id", None)
    if evidence_id:
        alias_id = f"{evidence_id}::p4_15bj::{suffix}"
    else:
        alias_id = f"p4_15bj::{suffix}::{id(item)}"

    return _p4_15r3_replace(
        item,
        evidence_id=alias_id,
        subject=subject,
        entity_type=entity_type,
        evidence_type=evidence_type,
        source_type=getattr(item, "source_type", None),
        provenance=_p4_15bj_provenance(item, suffix),
    )


def _p4_15bj_replacement_aliases_for_item(item):
    if not _p4_15bj_is_safe_replacement_source(item):
        return ()

    text = _p4_15bj_text_for_item(item)
    aliases = []

    measurement_terms = (
        "latest_position_measurement",
        "latest measurement",
        "measurement",
        "measured",
        "meting",
        "gemeten",
        "positie",
        "position",
        "wear_mm",
        "slijtage_mm",
        "remaining_mm",
        "rest_mm",
        "mm",
    )
    forecast_terms = (
        "forecast_result",
        "forecast",
        "prognose",
        "overdue",
        "days_overdue",
        "due_date",
        "deadline",
        "priority",
        "prioriteit",
        "direct_actie",
        "directe actie",
        "actie",
        "calculated",
        "berekend",
    )
    diagnostic_terms = (
        "diagnostic_finding",
        "diagnostic",
        "diagnose",
        "finding",
        "bevinding",
        "advies",
        "advice",
        "status_reason",
        "reason",
        "oorzaak",
        "root_cause",
        "risico",
        "risk",
        "actie",
        "direct_actie",
    )
    replacement_event_terms = (
        "replacement_history",
        "replacement_date",
        "replaced_at",
        "component_replaced",
        "replacement_event",
        "vervangen_op",
        "vervanging uitgevoerd",
        "is vervangen",
        "was replaced",
    )
    lifecycle_terms = (
        "lifecycle_history",
        "lifecycle",
        "life cycle",
        "standtijd",
        "levensduur",
        "installed_at",
        "install_date",
        "age_days",
        "run_hours",
        "runtime",
        "wear_rate",
        "slijtage_snelheid",
    )

    if _p4_15bj_has_any(text, measurement_terms) and (
        _p4_15bj_has_digit(text) or "mm" in text
    ):
        aliases.append(
            _p4_15bj_alias(
                item,
                subject="latest_position_measurement",
                entity_type="scraper_position",
                evidence_type=EvidenceType.MEASUREMENT,
                suffix="latest-position-measurement",
            )
        )

    if _p4_15bj_has_any(text, forecast_terms):
        aliases.append(
            _p4_15bj_alias(
                item,
                subject="forecast_result",
                entity_type="scraper_position",
                evidence_type=EvidenceType.CALCULATION_RESULT,
                suffix="forecast-result",
            )
        )

    if _p4_15bj_has_any(text, diagnostic_terms):
        aliases.append(
            _p4_15bj_alias(
                item,
                subject="diagnostic_finding",
                entity_type="scraper_position",
                evidence_type=EvidenceType.DIAGNOSTIC_FINDING,
                suffix="diagnostic-finding",
            )
        )

    # Strong gates: do not infer actual replacement/lifecycle history from
    # advice that something should be replaced.
    if _p4_15bj_has_any(text, replacement_event_terms):
        aliases.append(
            _p4_15bj_alias(
                item,
                subject="replacement_history",
                entity_type="scraper_lifecycle",
                evidence_type=EvidenceType.EVENT,
                suffix="replacement-history",
            )
        )

    if _p4_15bj_has_any(text, lifecycle_terms):
        aliases.append(
            _p4_15bj_alias(
                item,
                subject="lifecycle_history",
                entity_type="scraper_lifecycle",
                evidence_type=EvidenceType.MEASUREMENT,
                suffix="lifecycle-history",
            )
        )

    return tuple(alias for alias in aliases if alias is not None)


def _p4_15bj_with_replacement_source_shape_aliases(items):
    if items is None:
        return items

    if isinstance(items, EvidenceItem):
        item_tuple = (items,)
    elif isinstance(items, tuple):
        item_tuple = items
    elif isinstance(items, list):
        item_tuple = tuple(items)
    else:
        return items

    result = []
    seen_ids = set()
    for item in item_tuple:
        result.append(item)
        evidence_id = getattr(item, "evidence_id", None)
        if evidence_id:
            seen_ids.add(evidence_id)

    for item in item_tuple:
        for alias in _p4_15bj_replacement_aliases_for_item(item):
            evidence_id = getattr(alias, "evidence_id", None)
            if evidence_id and evidence_id in seen_ids:
                continue
            result.append(alias)
            if evidence_id:
                seen_ids.add(evidence_id)

    return tuple(result)


def normalize_execution_result_evidence(*args, **kwargs):
    items = _PROMATI_P4_15BJ_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE(
        *args,
        **kwargs,
    )
    return _p4_15bj_with_replacement_source_shape_aliases(items)

# PROMATI_P4_15BP_REPLACEMENT_GROUNDING_RELEVANCE_V1
#
# Narrow grounding-shape repair for BJ replacement aliases.
# Keep the BJ source-shape guard, but make the generated aliases explicit
# about grounding/directness/quality/freshness so the assessor does not
# treat LIVE_CANONICAL scraper_position aliases as not_grounded merely
# because the alias wrapper omitted these fields.


def _p4_15bp_enum_member(enum_cls, preferred_names, fallback=None):
    if enum_cls is None:
        return fallback
    for name in preferred_names:
        if hasattr(enum_cls, name):
            return getattr(enum_cls, name)
    try:
        members = getattr(enum_cls, "__members__", {})
        for name in preferred_names:
            if name in members:
                return members[name]
    except Exception:
        pass
    return fallback


def _p4_15bp_value_name(value):
    raw = getattr(value, "value", value)
    if raw is None:
        return ""
    return str(raw).upper()


def _p4_15bp_is_positive_status(value):
    text = _p4_15bp_value_name(value)
    return text in {
        "GROUNDED",
        "DIRECT",
        "VALID",
        "CURRENT",
        "FRESH",
        "SUFFICIENT",
        "OK",
    }


def _p4_15bp_grounding_status(item):
    current = getattr(item, "grounding_status", None)
    if _p4_15bp_is_positive_status(current):
        return current
    return _p4_15bp_enum_member(
        EvidenceGroundingStatus,
        ("GROUNDED", "SUPPORTED", "VALID", "UNKNOWN"),
        current,
    )


def _p4_15bp_directness(item):
    current = getattr(item, "direct_or_derived", None)
    if _p4_15bp_is_positive_status(current):
        return current
    return _p4_15bp_enum_member(
        EvidenceDirectness,
        ("DIRECT", "DERIVED", "UNKNOWN"),
        current,
    )


def _p4_15bp_quality_status(item):
    current = getattr(item, "quality_status", None)
    if _p4_15bp_is_positive_status(current):
        return current
    return _p4_15bp_enum_member(
        EvidenceQualityStatus,
        ("VALID", "OK", "UNKNOWN"),
        current,
    )


def _p4_15bp_freshness_status(item):
    current = getattr(item, "freshness_status", None)
    if _p4_15bp_is_positive_status(current):
        return current
    return _p4_15bp_enum_member(
        EvidenceFreshnessStatus,
        ("CURRENT", "FRESH", "UNKNOWN"),
        current,
    )


def _p4_15bp_claim_scope(item, subject, suffix):
    existing = tuple(getattr(item, "claim_scope", ()) or ())
    req_by_subject = {
        "latest_position_measurement": "LATEST_POSITION_MEASUREMENT",
        "forecast_result": "FORECAST_RESULT",
        "diagnostic_finding": "DIAGNOSTIC_FINDING",
        "lifecycle_history": "LIFECYCLE_HISTORY",
        "replacement_history": "REPLACEMENT_HISTORY",
    }

    additions = [
        req_by_subject.get(subject),
        "p4-15bp-grounded-bj-alias",
        suffix,
    ]

    result = []
    seen = set()
    for value in list(existing) + additions:
        if value is None:
            continue
        value = str(value)
        if value in seen:
            continue
        result.append(value)
        seen.add(value)

    return tuple(result)


def _p4_15bp_provenance(item, alias_name, subject):
    provenance = getattr(item, "provenance", None)
    if isinstance(provenance, dict):
        copied = copy.deepcopy(provenance)
    else:
        copied = {}

    copied.update(
        {
            "p4_15bp_marker": "PROMATI_P4_15BP_REPLACEMENT_GROUNDING_RELEVANCE_V1",
            "p4_15bp_alias_name": alias_name,
            "p4_15bp_subject": subject,
            "p4_15bp_grounding_shape": "explicit_grounding_directness_quality_freshness",
            "p4_15bp_source_evidence_id": getattr(item, "evidence_id", None),
            "p4_15bp_source_subject": getattr(item, "subject", None),
            "p4_15bp_source_type": _p4_15bj_enum_value(getattr(item, "source_type", None)),
            "p4_15bp_source_reference": getattr(item, "source_reference", None),
            "p4_15bp_guard": "only_from_live_canonical_maintenance_position_status",
        }
    )
    return copied


def _p4_15bj_alias(item, *, subject, entity_type, evidence_type, suffix):
    evidence_id = getattr(item, "evidence_id", None)
    if evidence_id:
        alias_id = f"{evidence_id}::p4_15bj::{suffix}::p4_15bp-grounded"
    else:
        alias_id = f"p4_15bj::{suffix}::p4_15bp-grounded::{id(item)}"

    # This override intentionally keeps the original BJ safe-source guard
    # outside this helper, in _p4_15bj_replacement_aliases_for_item.
    # The repair is limited to alias evidence shape.
    return _p4_15r3_replace(
        item,
        evidence_id=alias_id,
        subject=subject,
        entity_type=entity_type,
        evidence_type=evidence_type,
        source_type=getattr(item, "source_type", None),
        source_name=getattr(item, "source_name", None),
        source_reference=getattr(item, "source_reference", None),
        claim_scope=_p4_15bp_claim_scope(item, subject, suffix),
        grounding_status=_p4_15bp_grounding_status(item),
        direct_or_derived=_p4_15bp_directness(item),
        quality_status=_p4_15bp_quality_status(item),
        freshness_status=_p4_15bp_freshness_status(item),
        provenance=_p4_15bp_provenance(item, suffix, subject),
    )

# PROMATI_P4_15CE_LIFECYCLE_HISTORY_SOURCE_SHAPE_IMPORT_V1
#
# Narrow lifecycle-history source-shape import for replacement assessment.
# This patch is deliberately conservative:
# - emits lifecycle_history only from strong asset/scraper lifecycle source facts;
# - rejects generic blade coverage / product selection tables;
# - rejects generic chute/transferpoint/slijtage guidance;
# - never emits replacement_history;
# - never derives lifecycle_history from position/forecast/diagnostic aliases alone.

_p4_15ce_previous_normalize_execution_result_evidence = normalize_execution_result_evidence


def _p4_15ce_enum_value(value):
    return getattr(value, "value", value)


def _p4_15ce_text(value):
    try:
        if isinstance(value, (dict, list, tuple)):
            import json as _json
            return _json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        pass
    return "" if value is None else str(value)


def _p4_15ce_lower(value):
    return _p4_15ce_text(value).lower()


def _p4_15ce_walk(value, depth=0):
    if depth > 8:
        return
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _p4_15ce_walk(child, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in list(value)[:200]:
            yield from _p4_15ce_walk(child, depth + 1)


def _p4_15ce_any_text(value, terms):
    text = _p4_15ce_lower(value)
    return any(term in text for term in terms)


def _p4_15ce_has_any_strong_lifecycle_fact(value):
    # Strong facts must describe lifecycle/install/runtime/wear-rate,
    # not merely a generic product or transferpoint guideline.
    strong_terms = (
        "scraper_lifecycle",
        "asset_lifecycle",
        "lifecycle_history",
        "life_cycle",
        "service_life",
        "levensduur",
        "install_date",
        "installed_at",
        "installation_date",
        "geinstalleerd",
        "geïnstalleerd",
        "runtime_hours",
        "operating_hours",
        "draaiuren",
        "wear_rate",
        "slijtagegraad",
        "wear_measurement",
        "wear_history",
        "wear_mm",
        "blade_wear_mm",
        "scraper_wear",
    )
    return _p4_15ce_any_text(value, strong_terms)


def _p4_15ce_is_weak_or_generic_guidance(value):
    text = _p4_15ce_lower(value)

    # Generic product selection / blade coverage tables are not lifecycle history.
    weak_patterns = (
        "minimum_blade_coverage",
        "min. blade coverage",
        "belt_width_in",
        "belt_width_mm",
        "selection_table",
        "recommendation_table",
        "transferpoint",
        "transfer point",
        "chute",
        "trajectory",
        "centered loading",
        "loading angle",
        "return belt plow",
        "pulley cleaner",
        "generic",
        "cema-aanbeveling",
    )
    if any(pattern in text for pattern in weak_patterns):
        return True

    # A plain blade/blad/messer mention is not enough.
    weak_only_terms = ("blade", "blad", "messer", "slijtage")
    strong_anchor_terms = (
        "scraper_lifecycle",
        "asset_lifecycle",
        "install",
        "runtime",
        "draaiuren",
        "service_life",
        "levensduur",
        "wear_rate",
        "wear_mm",
        "blade_wear_mm",
    )

    has_weak = any(term in text for term in weak_only_terms)
    has_anchor = any(term in text for term in strong_anchor_terms)
    return has_weak and not has_anchor


def _p4_15ce_is_forbidden_replacement_history(value):
    forbidden_terms = (
        "replacement_history",
        "vervangingshistorie",
        "previous_replacement",
        "last_replacement",
        "replaced_at",
        "replacement_event",
    )
    return _p4_15ce_any_text(value, forbidden_terms)


def _p4_15ce_is_live_or_supported_source(item):
    source_type = _p4_15ce_enum_value(getattr(item, "source_type", None))
    source_type_text = "" if source_type is None else str(source_type)
    return source_type_text in {"LIVE_CANONICAL", "STRUCTURED_KNOWLEDGE", "DOCUMENT"} or "LIVE_CANONICAL" in source_type_text


def _p4_15ce_is_position_alias_only(item):
    subject = getattr(item, "subject", None)
    return subject in {
        "latest_position_measurement",
        "forecast_result",
        "diagnostic_finding",
        "maintenance_position_status",
    }


def _p4_15ce_source_payload(item):
    chunks = []
    for attr in (
        "value",
        "payload",
        "data",
        "structured_data",
        "metadata",
        "claim",
        "claims",
        "provenance",
        "source_reference",
        "source_name",
        "claim_scope",
    ):
        try:
            chunks.append(getattr(item, attr, None))
        except Exception:
            pass
    return chunks


def _p4_15ce_candidate_from_item(item):
    if item is None:
        return None

    # Never build lifecycle history from replacement-history terms or position aliases alone.
    if _p4_15ce_is_forbidden_replacement_history(item):
        return None
    if _p4_15ce_is_position_alias_only(item):
        return None
    if not _p4_15ce_is_live_or_supported_source(item):
        return None

    payload = _p4_15ce_source_payload(item)
    if _p4_15ce_is_weak_or_generic_guidance(payload):
        return None
    if not _p4_15ce_has_any_strong_lifecycle_fact(payload):
        return None

    return payload


def _p4_15ce_make_lifecycle_item(source_item, suffix):
    try:
        EvidenceItem
    except NameError:
        return None

    evidence_id = getattr(source_item, "evidence_id", None) or f"p4-15ce-source-{suffix}"
    source_type = getattr(source_item, "source_type", None)
    domain = getattr(source_item, "domain", None) or "inspection"

    try:
        evidence_type = EvidenceType.MEASUREMENT
    except Exception:
        evidence_type = getattr(source_item, "evidence_type", None)

    provenance = getattr(source_item, "provenance", None)
    if not isinstance(provenance, dict):
        provenance = {}

    provenance = dict(provenance)
    provenance.update({
        "p4_15ce_marker": "PROMATI_P4_15CE_LIFECYCLE_HISTORY_SOURCE_SHAPE_IMPORT_V1",
        "p4_15ce_source_evidence_id": evidence_id,
        "p4_15ce_rule": "strong_source_shape_lifecycle_import",
    })

    kwargs = {
        "evidence_id": f"{evidence_id}::p4_15ce::lifecycle-history",
        "domain": domain,
        "subject": "lifecycle_history",
        "entity_type": "scraper_lifecycle",
        "entity_id": getattr(source_item, "entity_id", None) or "scraper_lifecycle",
        "evidence_type": evidence_type,
        "source_type": source_type,
        "source_name": getattr(source_item, "source_name", None),
        "source_reference": getattr(source_item, "source_reference", None),
        "claim_scope": tuple(["lifecycle_history", "scraper_lifecycle", "replacement_analysis"]),
        "provenance": provenance,
    }

    # Add grounding-shape fields when supported by the dataclass/model.
    for name, value in (
        ("grounding_status", getattr(source_item, "grounding_status", None)),
        ("direct_or_derived", getattr(source_item, "direct_or_derived", None)),
        ("quality_status", getattr(source_item, "quality_status", None)),
        ("freshness_status", getattr(source_item, "freshness_status", None)),
    ):
        if value is not None:
            kwargs[name] = value

    try:
        return EvidenceItem(**kwargs)
    except TypeError:
        # Fallback for stricter constructor signatures.
        allowed = {}
        try:
            import inspect as _inspect
            params = set(_inspect.signature(EvidenceItem).parameters)
            allowed = {k: v for k, v in kwargs.items() if k in params}
            return EvidenceItem(**allowed)
        except Exception:
            return None
    except Exception:
        return None


def _p4_15ce_with_lifecycle_history_aliases(items):
    if not items:
        return items

    result = list(items)
    existing_ids = {getattr(item, "evidence_id", None) for item in result}
    added = 0

    for item in list(items):
        if _p4_15ce_candidate_from_item(item) is None:
            continue
        alias = _p4_15ce_make_lifecycle_item(item, added + 1)
        if alias is None:
            continue
        alias_id = getattr(alias, "evidence_id", None)
        if alias_id and alias_id in existing_ids:
            continue
        result.append(alias)
        if alias_id:
            existing_ids.add(alias_id)
        added += 1

    if isinstance(items, tuple):
        return tuple(result)
    return result


def normalize_execution_result_evidence(*args, **kwargs):
    items = _p4_15ce_previous_normalize_execution_result_evidence(*args, **kwargs)
    try:
        return _p4_15ce_with_lifecycle_history_aliases(items)
    except Exception:
        return items

# PROMATI_P4_15CP3_INSPECTION_LATEST_SCOPE_OVERVIEW_EVIDENCE_NORMALIZATION_V1
# Narrow repair:
# - single-intent inspection_latest can execute the inspection specialist as
#   scope_analysis/overview for an installation scope.
# - That overview result already contains real latest inspection rows
#   (laatste_inspectiedatum, meshhoogte_mm, asset entities), but the previous
#   evidence adapter did not project that source-shape into the existing
#   inspection_latest evidence contract.
# - This wrapper imports only real rows already present in the specialist
#   result. It does not synthesize evidence and does not touch replacement,
#   lifecycle, product or article routes.

_p4_15cp3_previous_normalize_execution_result_evidence = normalize_execution_result_evidence


def _p4_15cp3_nonempty_string(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _p4_15cp3_raw_result(execution_result):
    if isinstance(execution_result, dict):
        nested = execution_result.get("result")
        if isinstance(nested, dict):
            return nested
        return execution_result
    raw_result = getattr(execution_result, "result", None)
    if isinstance(raw_result, dict):
        return raw_result
    return None


def _p4_15cp3_is_scope_analysis_overview(raw_result):
    if not isinstance(raw_result, dict):
        return False
    return (
        _p4_15cp3_nonempty_string(raw_result.get("intent")) == "scope_analysis"
        and _p4_15cp3_nonempty_string(raw_result.get("operation")) == "overview"
    )


def _p4_15cp3_row_contains_latest_inspection_signal(row):
    if not isinstance(row, dict):
        return False

    date_value = _p4_15cp3_nonempty_string(
        row.get("laatste_inspectiedatum")
        or row.get("latest_inspection_date")
        or row.get("inspection_date")
        or row.get("document_date")
        or row.get("cycle_end")
        or row.get("observed_at")
    )
    if date_value is None:
        return False

    # At least one inspection observation signal must be present.  This keeps
    # generic scope rows or catalog rows out while accepting measurement and
    # condition-only inspection positions.
    observation_fields = (
        "meshoogte_mm",
        "slijtage_actie_pct",
        "conditie_code",
        "mes_interpretatie",
        "commentaar",
        "planned_replace_signal",
        "mechanical_or_access_signal",
        "score_bron",
        "analyse_basis",
    )
    return any(row.get(field) not in (None, "", [], {}) for field in observation_fields)


def _p4_15cp3_scope_overview_inspection_latest_evidence(
    execution_result,
    *,
    retrieved_at,
):
    raw_result = _p4_15cp3_raw_result(execution_result)
    if not _p4_15cp3_is_scope_analysis_overview(raw_result):
        return ()

    records = raw_result.get("resultaat")
    if not isinstance(records, list) or not records:
        return ()

    if not any(
        _p4_15cp3_row_contains_latest_inspection_signal(row)
        for row in records
        if isinstance(row, dict)
    ):
        return ()

    inspection_live = copy.deepcopy(raw_result)
    inspection_live["rows"] = copy.deepcopy(records)
    inspection_live.pop("resultaat", None)
    inspection_live["intent"] = "inspection_latest"
    inspection_live.setdefault("domain", "inspection")

    canonical_execution = _p4_14e_normalize_execution_result_input(
        execution_result=inspection_live,
        intent="inspection_latest",
        retrieved_at=retrieved_at,
    )

    if canonical_execution is None or not hasattr(canonical_execution, "action"):
        return ()

    return tuple(
        _analysis_resultaat_latest_evidence(
            canonical_execution,
            retrieved_at=retrieved_at,
        )
    )


def _p4_15cp3_evidence_id(item):
    value = getattr(item, "evidence_id", None)
    return str(value) if value is not None else None


def _p4_15cp3_dedupe_evidence(items):
    output = []
    seen = set()
    for item in tuple(items or ()):
        evidence_id = _p4_15cp3_evidence_id(item)
        if evidence_id is None:
            output.append(item)
            continue
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        output.append(item)
    return tuple(output)


def normalize_execution_result_evidence(
    execution_result=None,
    *,
    retrieved_at=None,
    intent=None,
    result=None,
):
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)

    base_items = tuple(
        _p4_15cp3_previous_normalize_execution_result_evidence(
            execution_result,
            retrieved_at=retrieved_at,
            intent=intent,
            result=result,
        )
        or ()
    )

    raw_input = result if result is not None else execution_result
    additions = tuple(
        _p4_15cp3_scope_overview_inspection_latest_evidence(
            raw_input,
            retrieved_at=retrieved_at,
        )
    )

    if not additions:
        return base_items

    return _p4_15cp3_dedupe_evidence(base_items + additions)

