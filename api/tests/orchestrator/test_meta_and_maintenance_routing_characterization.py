"""Current routing observations plus separately registered desired contracts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.orchestrator.query_classification import classify_query
from app.orchestrator.understanding import understand_query


GAPS = Path(__file__).resolve().parents[1] / "fixtures" / "pre_refactor_known_gaps.json"


def _value(value): return getattr(value, "value", value)


@pytest.mark.parametrize(("question", "query_class", "domains", "intent"), [
    ("kan je een uitgebreide test set ontwerpen die deze zaken ook gaat afdekken", "business", [], "unknown"),
    ("hoe complex is de orchestrator om te maken", "system_meta", ["diagnostics"], "diagnostics_overview"),
    ("welke zwakke plekken zitten er in service.py", "business", [], "unknown"),
    ("hoe moet ik de pipeline opdelen zonder gedragswijziging", "business", [], "unknown"),
    ("welke endpoints moet de orchestrator gebruiken voor maintenance", "system_meta", ["diagnostics"], "diagnostics_overview"),
])
def test_meta_questions_lock_current_classifier_and_understanding(question, query_class, domains, intent):
    plan = understand_query(question)
    assert _value(classify_query(question)) == query_class
    assert [_value(item) for item in plan.domains] == domains
    assert plan.intent == intent


@pytest.mark.parametrize("question", [
    "Wat is de laatste inspectiestatus van A319?",
    "Kan je de slijtage van de schrapers op A319 analyseren?",
])
def test_business_inspection_questions_remain_separate(question):
    plan = understand_query(question)
    assert _value(plan.query_class) == "business"
    assert "inspection" in [_value(item) for item in plan.domains]


@pytest.mark.parametrize(("phrase", "blockers"), [
    ("3 mm", []), ("de 3 mm", ["DE3"]), ("rond de 3mm", []),
    ("drie millimeter", []), ("op of onder 3 mm", []),
])
def test_gsl_threshold_variants_lock_current_false_de3_gap(phrase, blockers):
    plan = understand_query(f"toon GSL schrapers {phrase} vervanggrens")
    assert [_value(item) for item in plan.domains] == []
    assert plan.intent == "unknown"
    assert plan.clarification_required is True
    assert "band_code" not in plan.entities
    assert [item.candidate_value for item in plan.execution_blockers] == blockers


def test_real_band_a319_survives_next_to_threshold_without_threshold_entity():
    plan = understand_query("toon voor band A319 de posities rond de 3 mm grens")
    assert plan.entities["band_code"].value == "A319"
    assert "threshold" not in plan.entities and "meshoogte_threshold" not in plan.entities


@pytest.mark.parametrize(("question", "domains", "intents"), [
    ("geef de schrapers in GSL rond de 3 mm grens", [], []),
    ("toon de 20 meest urgente schraperposities", ["inspection"], ["product_lookup"]),
    ("wat moet eerst vervangen worden in GSL", ["inspection"], ["maintenance_priority", "inspection_latest"]),
    ("welke banden hebben direct aandacht nodig qua meshoogte", ["inspection"], ["inspection_lookup"]),
])
def test_maintenance_false_domain_expansion_is_characterized(question, domains, intents):
    plan = understand_query(question)
    assert [_value(item) for item in plan.domains] == domains
    assert [task.intent for task in plan.intent_tasks] == intents


def test_future_contracts_are_machine_readable_and_not_implemented():
    gaps = json.loads(GAPS.read_text(encoding="utf-8"))
    ids = {gap["id"] for gap in gaps["gaps"]}
    assert {"META_QUESTIONS_NOT_DEVELOPMENT_CLASS", "GSL_3MM_FALSE_DE3",
            "MAINTENANCE_FALSE_DOMAIN_EXPANSION", "MAINTENANCE_CAPABILITY_CONTRACT"} <= ids
    capability = next(g for g in gaps["gaps"] if g["id"] == "MAINTENANCE_CAPABILITY_CONTRACT")
    assert capability["desired_future"]["capability_id"] == "analysis.maintenance_positions.v1"
    assert capability["desired_future"]["public_projection"] == "maintenance_position_public_list_v1"
    assert capability["removal_condition"]


@pytest.mark.xfail(
    strict=True,
    reason="GAP-ID MAINTENANCE_CAPABILITY_CONTRACT: remove when the catalog module and route contract exist",
)
def test_future_capability_catalog_contract_strict_xfail_without_collection_error():
    from app.orchestrator.endpoint_capability_catalog import ANALYSIS_MAINTENANCE_POSITIONS
    assert ANALYSIS_MAINTENANCE_POSITIONS.id == "analysis.maintenance_positions.v1"
