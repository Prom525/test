"""Pre-refactor contract for the exported orchestrator facade.

These tests intentionally protect the current wrapper stack.  They do not
endorse the post-CP12 repairs as the desired architecture.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.orchestrator import service


SERVICE_PATH = Path(service.__file__)


def _definitions_and_bindings():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8-sig"))
    definitions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_orchestrator"
    ]
    bindings = [
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Name)
        and node.value.id == "run_orchestrator"
        and "previous_run_orchestrator" in node.targets[0].id
    ]
    return definitions, bindings


def test_four_top_level_facades_and_symbolic_previous_bindings_are_exact():
    definitions, bindings = _definitions_and_bindings()
    assert len(definitions) == 4
    assert bindings == [
        "_p4_15cp3c_previous_run_orchestrator",
        "_p4_15cp4b_previous_run_orchestrator",
        "_p4_15cp4f_previous_run_orchestrator",
    ]


def test_exported_facade_is_fourth_and_chain_is_cp4f_cp4b_cp3c_core():
    definitions, _ = _definitions_and_bindings()
    assert service.run_orchestrator.__code__.co_firstlineno == definitions[3].lineno
    cp4b = service._p4_15cp4f_previous_run_orchestrator
    cp3c = service._p4_15cp4b_previous_run_orchestrator
    core = service._p4_15cp3c_previous_run_orchestrator
    assert cp4b is not cp3c and cp3c is not core
    assert cp4b.__code__.co_names[0] == "_p4_15cp4b_previous_run_orchestrator"
    assert cp3c.__code__.co_names[0] == "_p4_15cp3c_previous_run_orchestrator"


@pytest.mark.parametrize(
    ("wrapper", "previous_name", "marker"),
    [
        (service._p4_15cp4b_previous_run_orchestrator,
         "_p4_15cp3c_previous_run_orchestrator", "cp3c"),
        (service._p4_15cp4f_previous_run_orchestrator,
         "_p4_15cp4b_previous_run_orchestrator", "cp4b"),
        (service.run_orchestrator,
         "_p4_15cp4f_previous_run_orchestrator", "cp4f"),
    ],
)
def test_each_facade_wrapper_calls_its_predecessor_once(
    monkeypatch, wrapper, previous_name, marker
):
    calls = []
    sentinel = {"status": "ok", "answer": "unchanged"}

    def previous(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(service, previous_name, previous)
    result = wrapper("payload", include_trace=False)
    assert calls == [(('payload',), {"include_trace": False})]
    assert result["answer"] == "unchanged"
    assert not any(marker in key for key in result)

