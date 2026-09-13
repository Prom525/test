"""Lock the mechanically fragile evidence-adapter override chain."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.orchestrator import evidence_adapters as adapters


PREVIOUS = [
    "_PROMATI_P4_15R3_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15S_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15T7_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15U42_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15W5_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15Y4_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_PROMATI_P4_15BJ_ORIGINAL_NORMALIZE_EXECUTION_RESULT_EVIDENCE",
    "_p4_15ce_previous_normalize_execution_result_evidence",
    "_p4_15cp3_previous_normalize_execution_result_evidence",
]


def _normalizer_definitions():
    tree = ast.parse(Path(adapters.__file__).read_text(encoding="utf-8-sig"))
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == "normalize_execution_result_evidence"]


def test_ten_definitions_active_export_and_symbolic_chain_are_exact():
    definitions = _normalizer_definitions()
    assert len(definitions) == 10
    assert adapters.normalize_execution_result_evidence.__code__.co_firstlineno == definitions[-1].lineno
    functions = [getattr(adapters, name) for name in PREVIOUS]
    assert [fn.__code__.co_firstlineno for fn in functions] == [node.lineno for node in definitions[:-1]]


@pytest.mark.parametrize("index", range(9))
def test_each_evidence_wrapper_calls_its_predecessor_once(monkeypatch, index):
    wrapper = (getattr(adapters, PREVIOUS[index + 1])
               if index < 8 else adapters.normalize_execution_result_evidence)
    previous_name = PREVIOUS[index]
    calls = []
    monkeypatch.setattr(adapters, previous_name,
                        lambda *args, **kwargs: calls.append((args, kwargs)) or ())
    result = wrapper({"status": "ok"})
    assert len(calls) == 1
    assert isinstance(result, tuple)


def test_cp3_tail_deduplicates_by_evidence_id_and_preserves_order():
    class Item:
        def __init__(self, evidence_id): self.evidence_id = evidence_id
    first, duplicate, second = Item("stable-a"), Item("stable-a"), Item("stable-b")
    assert adapters._p4_15cp3_dedupe_evidence((first, duplicate, second)) == (first, second)


def test_representative_domain_adapters_remain_registered_in_source_shape():
    source = Path(adapters.__file__).read_text(encoding="utf-8-sig")
    protected = (
        "product", "inspection_latest", "lifecycle_history",
        "maintenance_position_status", "replacement_history", "technical",
        "org", "rfq", "diagnostic",
    )
    assert all(token in source.casefold() for token in protected)

