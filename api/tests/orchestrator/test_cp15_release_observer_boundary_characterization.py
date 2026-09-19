"""Characterize the service-owned CP15 release-observer boundary."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class StopAfterCP15(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class ReleaseWriteProbe(dict):
    def __init__(self, initial=(), *, failures=()):
        super().__init__(initial)
        self.failures = iter(failures)
        self.release_attempts = []

    def __setitem__(self, key, value):
        if key == "release_gate_cp15":
            self.release_attempts.append(value)
            failure = next(self.failures, None)
            if failure is not None:
                raise failure
        super().__setitem__(key, value)


_DEFAULT = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_cp12_concise_composition_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("cp12_3z2d_for_3z1e", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=ReleaseWriteProbe,
    builder_return=_DEFAULT,
    builder_error=None,
    observability_error=_DEFAULT,
):
    prior = _prior_characterization()
    pipeline = pipeline_factory() if callable(pipeline_factory) else pipeline_factory
    h = prior._install(monkeypatch, pipeline_factory=pipeline)
    calls, events = h.calls, h.events
    builder_value = object() if builder_return is _DEFAULT else builder_return
    stop = StopAfterCP15("controlled post-CP15 stop boundary")
    after_error = stop if observability_error is _DEFAULT else observability_error

    def builder(*args, **kwargs):
        events.append("cp15")
        calls.append(("cp15", args, kwargs))
        shadow_before_cp15 = args[0]
        calls.append(("cp15_shadow_before", shadow_before_cp15, {}))
        if builder_error is not None:
            raise builder_error
        return builder_value

    def after(*args, **kwargs):
        events.append("observability")
        calls.append(("observability", args, kwargs))
        raise after_error

    monkeypatch.setattr(service, "build_release_gate_cp15", builder)
    monkeypatch.setattr(
        service, "_record_task_execution_plan_shadow_observability", after
    )
    before = {
        "plan": dict(vars(h.plan)),
        "results": list(h.results),
        "typed": list(h.typed),
        "trace": dict(h.trace),
        "legacy": h.legacy,
    }
    namespace = dict(vars(h))
    namespace.update(locals())
    return SimpleNamespace(**namespace)


def _run(h, exception=StopAfterCP15):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


def _service_locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            local = traceback.tb_frame.f_locals
            if "task_execution_shadow" in local:
                return local
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


@pytest.mark.parametrize("factory", [ReleaseWriteProbe, DictSubclass])
def test_dict_gate_accepts_dict_family_and_orders_3z2d_cp15_observability(
    monkeypatch, factory
):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    error = _run(h)
    local = _service_locals(error)
    assert local["evidence_pipeline"] is pipeline
    assert h.events.index("cp11") < h.events.index("cp12") < h.events.index("cp15")
    assert h.events.index("cp15") < h.events.index("observability")
    assert [len(_calls(h, name)) for name in ("cp11", "cp12", "cp15", "observability")] == [1] * 4


@pytest.mark.parametrize("factory", [UserDict, list, tuple, lambda: None, object])
def test_dict_gate_rejects_non_dict_and_skips_3z2c_3z2d_cp15(monkeypatch, factory):
    h = _install(monkeypatch, pipeline_factory=factory())
    assert _run(h) is h.stop
    assert not _calls(h, "cp11") and not _calls(h, "cp12") and not _calls(h, "cp15")
    assert len(_calls(h, "observability")) == 1


@pytest.mark.parametrize("returned", [{"x": 1}, [1], (1,), None, object()])
def test_success_runtime_resolved_exact_call_and_identity_preserving_write(
    monkeypatch, returned
):
    preserved = object()
    pipeline = ReleaseWriteProbe({"preserved": preserved})
    h = _install(monkeypatch, pipeline_factory=pipeline, builder_return=returned)
    error = _run(h)
    call = _calls(h, "cp15")[0]
    local = _service_locals(error)
    assert call[1] == (local["task_execution_shadow"], pipeline)
    assert call[1][0] is local["task_execution_shadow"] and call[1][1] is pipeline
    assert call[2] == {}
    assert pipeline.release_attempts == [returned]
    assert pipeline["release_gate_cp15"] is returned
    assert pipeline["preserved"] is preserved and local["evidence_pipeline"] is pipeline


class FirstInternalError(RuntimeError):
    pass


class SecondInternalError(ValueError):
    pass


@pytest.mark.parametrize("error", [FirstInternalError("a"), SecondInternalError("b")])
def test_exception_fallback_exact_shape_type_and_single_builder_call(monkeypatch, error):
    h = _install(monkeypatch, builder_error=error)
    _run(h)
    fallback = h.pipeline["release_gate_cp15"]
    assert fallback == {
        "contract_version": "promati.orchestrator.release_gate.cp15.v1",
        "evaluated": False,
        "release_allowed": False,
        "public_authoritative": False,
        "blocking_reasons": ["cp15_internal_error_fail_closed"],
        "blocked_gate_ids": ["cp15"],
        "internal_error_type": type(error).__name__,
    }
    assert set(fallback) == {
        "contract_version", "evaluated", "release_allowed", "public_authoritative",
        "blocking_reasons", "blocked_gate_ids", "internal_error_type",
    }
    assert fallback["blocking_reasons"] is not fallback["blocked_gate_ids"]
    assert len(_calls(h, "cp15")) == len(_calls(h, "observability")) == 1


def test_fallback_state_and_lists_are_fresh_across_core_calls(monkeypatch):
    first = _install(monkeypatch, builder_error=RuntimeError("first"))
    _run(first)
    second = _install(monkeypatch, builder_error=RuntimeError("second"))
    _run(second)
    one, two = (h.pipeline["release_gate_cp15"] for h in (first, second))
    assert one is not two
    assert one["blocking_reasons"] is not two["blocking_reasons"]
    assert one["blocked_gate_ids"] is not two["blocked_gate_ids"]


def test_builder_baseexception_propagates_identically_without_write_or_stop(monkeypatch):
    fatal = Fatal("builder")
    h = _install(monkeypatch, builder_error=fatal)
    assert _run(h, Fatal) is fatal
    assert not h.pipeline.release_attempts and not _calls(h, "observability")
    assert len(_calls(h, "cp15")) == 1


def test_first_success_write_exception_is_caught_then_fallback_write_succeeds(monkeypatch):
    failure = RuntimeError("first write")
    returned = object()
    pipeline = ReleaseWriteProbe(failures=[failure])
    h = _install(monkeypatch, pipeline_factory=pipeline, builder_return=returned)
    _run(h)
    assert pipeline.release_attempts[0] is returned
    fallback = pipeline.release_attempts[1]
    assert fallback is pipeline["release_gate_cp15"]
    assert fallback["internal_error_type"] == "RuntimeError"
    assert len(pipeline.release_attempts) == 2 and len(_calls(h, "cp15")) == 1
    assert len(_calls(h, "observability")) == 1


@pytest.mark.parametrize("second", [RuntimeError("fallback"), Fatal("fallback")])
def test_failing_fallback_write_propagates_second_error_without_retry(monkeypatch, second):
    first = RuntimeError("success write")
    returned = object()
    pipeline = ReleaseWriteProbe(failures=[first, second])
    h = _install(monkeypatch, pipeline_factory=pipeline, builder_return=returned)
    assert _run(h, type(second)) is second
    assert pipeline.release_attempts[0] is returned
    assert pipeline.release_attempts[1]["internal_error_type"] == "RuntimeError"
    assert len(pipeline.release_attempts) == 2
    assert "release_gate_cp15" not in pipeline and not _calls(h, "observability")


def test_success_write_baseexception_is_not_caught(monkeypatch):
    fatal = Fatal("success write")
    returned = object()
    pipeline = ReleaseWriteProbe(failures=[fatal])
    h = _install(monkeypatch, pipeline_factory=pipeline, builder_return=returned)
    assert _run(h, Fatal) is fatal
    assert pipeline.release_attempts == [returned]
    assert len(_calls(h, "cp15")) == 1 and not _calls(h, "observability")


def test_builder_exception_precedes_lazy_fallback_construction(monkeypatch):
    error = RuntimeError("builder")
    pipeline = ReleaseWriteProbe()
    h = _install(monkeypatch, pipeline_factory=pipeline, builder_error=error)
    _run(h)
    assert h.events.index("cp15") < h.events.index("observability")
    assert pipeline.release_attempts[0]["internal_error_type"] == type(error).__name__


def test_cp15_preserves_upstream_state_answer_authority_and_shadow(monkeypatch):
    h = _install(monkeypatch)
    error = _run(h)
    local = _service_locals(error)
    assert (dict(vars(h.plan)), h.results, h.typed, h.trace, h.legacy) == (
        h.before["plan"], h.before["results"], h.before["typed"],
        h.before["trace"], h.before["legacy"],
    )
    assert local["answer"] is h.returned[0]
    assert local["task_public_composition_authority_p4_6f"] is h.authority_value
    shadow_before = _calls(h, "cp15_shadow_before")[0][1]
    assert local["task_execution_shadow"] is shadow_before


def test_observability_sentinel_does_not_repeat_upstream_or_cp15(monkeypatch):
    sentinel = StopAfterCP15("unique")
    h = _install(monkeypatch, observability_error=sentinel)
    assert _run(h) is sentinel
    for name in ("shadow", "canary", "3z2a", "cp11", "cp12", "cp15", "observability"):
        assert len(_calls(h, name)) == 1


@pytest.mark.parametrize("builder_error", [None, RuntimeError("fallback")])
def test_success_and_fallback_reach_observability_with_existing_state(
    monkeypatch, builder_error
):
    h = _install(monkeypatch, builder_error=builder_error)
    error = _run(h)
    local = _service_locals(error)
    call = _calls(h, "observability")[0]
    assert call[1] == (local["counts"], h.plan, h.pipeline)
    assert call[1][0] is local["counts"]
    assert call[1][1] is h.plan and call[1][2] is h.pipeline
    assert call[2] == {}


def test_ast_future_3z2e_boundary_exact_gate_try_call_writes_and_fallback_shape():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "run_orchestrator"
    )
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]

    def named(name):
        return [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == name]

    cp12 = named("run_cp12_concise_composition_stage")
    cp15 = named("run_cp15_release_observer_stage")
    after = named("_record_task_execution_plan_shadow_observability")
    assert tuple(map(len, (cp12, cp15, after))) == (1, 1, 1)
    assert cp12[0].lineno < cp15[0].lineno < after[0].lineno
    gate = next(n for n in function.body if isinstance(n, ast.If) and cp15[0] in ast.walk(n))
    assert ast.unparse(gate.test) == "isinstance(evidence_pipeline, dict)"
    assert [ast.unparse(arg) for arg in cp15[0].args] == [
        "task_execution_shadow", "evidence_pipeline"
    ]
    assert [(kw.arg, ast.unparse(kw.value)) for kw in cp15[0].keywords] == [
        ("build_release_gate_cp15", "build_release_gate_cp15")
    ]
    binding = next(n for n in gate.body if isinstance(n, ast.Assign)
                   and ast.unparse(n.targets[0]) == "evidence_pipeline"
                   and isinstance(n.value, ast.Attribute)
                   and isinstance(n.value.value, ast.Name)
                   and n.value.value.id == "cp15_release_observer_stage_result"
                   and n.value.attr == "evidence_pipeline")
    assert binding.lineno > cp15[0].lineno
