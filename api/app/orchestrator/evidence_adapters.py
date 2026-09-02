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

        row_matches_asset = (
            asset_resolved
            and row_band_code is not None
            and asset_band_code is not None
            and row_band_code
            == asset_band_code
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
    # --------------------------------------------------------

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

        row_matches_asset = (
            asset_band_code is not None
            and row_band_code == asset_band_code
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
            subject="latest_blade_height",
            entity_type="scraper_position",
            entity_id=entity_id,
            evidence_type=EvidenceType.MEASUREMENT,
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

def normalize_execution_result_evidence(
    execution_result: ExecutionResult,
    *,
    retrieved_at: datetime,
) -> tuple[EvidenceItem, ...]:
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