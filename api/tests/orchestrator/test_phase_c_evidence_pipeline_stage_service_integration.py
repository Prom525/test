import ast
import importlib.util
from pathlib import Path

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_evidence_pipeline_stage import (
    PhaseCEvidencePipelineStageResult,
)


def _characterization():
    path = Path(__file__).with_name(
        "test_phase_c_evidence_pipeline_assembly_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3u1_for_3u2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_dependencies_single_call_direct_binding_and_next_boundary(monkeypatch):
    characterized = _characterization()
    h = characterized._install(monkeypatch, stop=False)
    evidence_pipeline = object()
    calls = []
    boundary = characterized.StopAfterAssembly("following boundary")

    def stage(*args, **kwargs):
        calls.append((args, kwargs))
        return PhaseCEvidencePipelineStageResult(evidence_pipeline)

    monkeypatch.setattr(service, "run_phase_c_evidence_pipeline_stage", stage)
    monkeypatch.setattr(
        service,
        "_build_user_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(boundary),
    )
    raised = characterized._run(h)
    assert raised is boundary
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (h.requirement_set,)
    expected = characterized._expected(h)
    assert set(kwargs) == set(characterized.KEYS[1:]) | {
        "evidence_pipeline_to_dict"
    }
    assert all(kwargs[key] is expected[key] for key in characterized.KEYS[1:])
    assert kwargs["evidence_pipeline_to_dict"] is service._evidence_pipeline_to_dict
    assert characterized._service_locals(raised)["evidence_pipeline"] is evidence_pipeline
    assert h.mapping_calls == []


@pytest.mark.parametrize("fatal", [False, True])
def test_stage_exception_preserves_outer_fail_open_none_and_baseexception(
        monkeypatch, fatal):
    characterized = _characterization()
    h = characterized._install(monkeypatch)
    error = characterized.Fatal("fatal") if fatal else RuntimeError("ordinary")

    def stage(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "run_phase_c_evidence_pipeline_stage", stage)
    raised = characterized._run(
        h,
        characterized.Fatal if fatal else h.base.base.base.characterized.StopOnLegacyPath,
    )
    if fatal:
        assert raised is error
    else:
        assert characterized._service_locals(raised)["evidence_pipeline"] is None
    assert h.mapping_calls == []
    names = [row[0] for row in h.base.base.base.h.calls]
    assert names.count("legacy_path") == (0 if fatal else 1)


def test_leaf_imports_one_ordered_callsite_direct_binding_and_no_inline_mapping():
    root = Path(__file__).parents[2]
    leaf = ast.parse(
        (root / "app/orchestrator/phase_c_evidence_pipeline_stage.py").read_text()
    )
    imports = {
        alias.name
        for node in leaf.body if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module for node in leaf.body if isinstance(node, ast.ImportFrom)
    }
    assert imports == {"dataclasses", "typing"}

    tree = ast.parse((root / "app/orchestrator/service.py").read_text())
    calls = {
        name: [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ]
        for name in (
            "run_phase_c_synthesis_stage",
            "run_phase_c_evidence_pipeline_stage",
            "_evidence_pipeline_to_dict",
        )
    }
    assert len(calls["run_phase_c_synthesis_stage"]) == 1
    assert len(calls["run_phase_c_evidence_pipeline_stage"]) == 1
    assert calls["_evidence_pipeline_to_dict"] == []
    stage_call = calls["run_phase_c_evidence_pipeline_stage"][0]
    assert [arg.id for arg in stage_call.args] == ["requirement_set"]
    assert [keyword.arg for keyword in stage_call.keywords] == [
        *list(_characterization().KEYS[1:]), "evidence_pipeline_to_dict"
    ]
    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "evidence_pipeline"
                for target in node.targets)
    ]
    assert any(
        isinstance(node.value, ast.Attribute)
        and node.value.attr == "evidence_pipeline"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "phase_c_evidence_pipeline_stage"
        for node in assignments
    )
    assert (
        calls["run_phase_c_synthesis_stage"][0].lineno
        < stage_call.lineno
        < min(node.lineno for node in assignments if node.lineno > stage_call.lineno)
    )
