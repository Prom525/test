"""Characterize the two service-owned post-CP15 observability boundaries."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


_NEW_OBSERVABILITY_COUNTS = service._new_observability_counts


class StopAtResponseBuildClock(BaseException):
    pass


class Fatal(BaseException):
    pass


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_cp15_release_observer_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("cp15_3z2e_for_3aa1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=None,
    plan_shadow=None,
    release=None,
    clock_error=None,
):
    prior = _prior_characterization()
    kwargs = {} if pipeline_factory is None else {"pipeline_factory": pipeline_factory}
    h = prior._install(monkeypatch, **kwargs)
    calls, events = h.calls, h.events
    stop = StopAtResponseBuildClock("controlled response-build clock boundary")
    clock_failure = stop if clock_error is None else clock_error

    def first(*args, **kwargs):
        events.append("plan_shadow_observability")
        calls.append(("plan_shadow_observability", args, kwargs))
        if plan_shadow is not None:
            return plan_shadow(*args, **kwargs)

    def second(*args, **kwargs):
        events.append("release_observability")
        calls.append(("release_observability", args, kwargs))
        if release is not None:
            return release(*args, **kwargs)

    def clock():
        # The service uses the same runtime-resolved clock at earlier metrics
        # boundaries. Stop only at the first call after both characterized
        # helpers, which is the response-build assignment under test.
        if _calls(SimpleNamespace(calls=calls), "release_observability"):
            events.append("response_build_clock")
            calls.append(("response_build_clock", (), {}))
            raise clock_failure
        calls.append(("earlier_observability_clock", (), {}))
        return 1.0

    monkeypatch.setattr(
        service, "_record_task_execution_plan_shadow_observability", first
    )
    monkeypatch.setattr(
        service, "_record_public_composition_canary_release_observability", second
    )
    monkeypatch.setattr(service, "_observability_now", clock)
    namespace = dict(vars(h))
    namespace.update(locals())
    return SimpleNamespace(**namespace)


def _run(h, exception=StopAtResponseBuildClock):
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
            if "response_build_started" not in local and "counts" in local:
                return local
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


@pytest.mark.parametrize("pipeline_factory", [None, lambda: ["non-dict"]])
def test_exact_order_runtime_resolution_arguments_and_dict_gate(
    monkeypatch, pipeline_factory
):
    h = _install(monkeypatch, pipeline_factory=pipeline_factory)
    error = _run(h)
    local = _service_locals(error)
    first = _calls(h, "plan_shadow_observability")[0]
    second = _calls(h, "release_observability")[0]
    for call in (first, second):
        assert call[1] == (local["counts"], h.plan, h.pipeline)
        assert call[1][0] is local["counts"]
        assert call[1][1] is h.plan and call[1][2] is h.pipeline
        assert call[2] == {}
    expected = ["plan_shadow_observability", "release_observability",
                "response_build_clock"]
    observed = [event for event in h.events if event in expected]
    assert observed == expected
    assert len(_calls(h, "cp15")) == (0 if pipeline_factory else 1)


@pytest.mark.parametrize("failing", ["first", "second", "both"])
def test_each_exception_zone_is_independent_and_mutations_survive(
    monkeypatch, failing
):
    seen = []

    def first(counts, plan, pipeline):
        counts["first_partial"] = 1
        seen.append((counts, plan, pipeline, dict(counts)))
        if failing in {"first", "both"}:
            raise RuntimeError("first")
        return counts

    def second(counts, plan, pipeline):
        seen.append((counts, plan, pipeline, dict(counts)))
        counts["second_partial"] = 2
        if failing in {"second", "both"}:
            raise ValueError("second")
        return plan

    h = _install(monkeypatch, plan_shadow=first, release=second)
    local = _service_locals(_run(h))
    assert len(seen) == 2
    assert seen[0][0] is seen[1][0] is local["counts"]
    assert seen[1][3]["first_partial"] == 1
    assert local["counts"]["first_partial"] == 1
    assert local["counts"]["second_partial"] == 2
    assert len(_calls(h, "response_build_clock")) == 1


@pytest.mark.parametrize("failing", ["first", "second"])
def test_baseexception_propagates_identically_and_stops_later_calls(
    monkeypatch, failing
):
    fatal = Fatal(failing)

    def first(*args):
        if failing == "first":
            raise fatal

    def second(*args):
        if failing == "second":
            raise fatal

    h = _install(monkeypatch, plan_shadow=first, release=second)
    assert _run(h, Fatal) is fatal
    assert len(_calls(h, "plan_shadow_observability")) == 1
    assert len(_calls(h, "release_observability")) == (failing == "second")
    assert not _calls(h, "response_build_clock")


@pytest.mark.parametrize("returned", [object(), {"replacement": True}, None])
def test_helper_return_values_are_ignored(monkeypatch, returned):
    h = _install(
        monkeypatch,
        plan_shadow=lambda *args: returned,
        release=lambda *args: returned,
    )
    local = _service_locals(_run(h))
    assert local["plan"] is h.plan
    assert local["evidence_pipeline"] is h.pipeline
    assert len(_calls(h, "response_build_clock")) == 1


def test_counts_are_fresh_across_core_calls(monkeypatch):
    identities = []
    first = _install(monkeypatch, plan_shadow=lambda counts, *_: identities.append(counts))
    monkeypatch.setattr(service, "_new_observability_counts", _NEW_OBSERVABILITY_COUNTS)
    _run(first)
    second = _install(monkeypatch, plan_shadow=lambda counts, *_: identities.append(counts))
    monkeypatch.setattr(service, "_new_observability_counts", _NEW_OBSERVABILITY_COUNTS)
    _run(second)
    assert len(identities) == 2 and identities[0] is not identities[1]


def test_service_boundary_does_not_mutate_plan_or_non_dict_pipeline(monkeypatch):
    pipeline = [object()]
    snapshots = []

    def observe(counts, plan, evidence_pipeline):
        snapshots.append((dict(vars(plan)), list(evidence_pipeline)))

    h = _install(
        monkeypatch, pipeline_factory=pipeline, plan_shadow=observe, release=observe
    )
    _run(h)
    assert snapshots[0] == snapshots[1]
    assert vars(h.plan) == snapshots[0][0]
    assert pipeline == snapshots[0][1]


@pytest.mark.parametrize("error", [RuntimeError("clock"), Fatal("clock")])
def test_response_build_clock_is_stop_boundary_and_does_not_retry(error, monkeypatch):
    h = _install(monkeypatch, clock_error=error)
    assert _run(h, type(error)) is error
    assert len(_calls(h, "plan_shadow_observability")) == 1
    assert len(_calls(h, "release_observability")) == 1
    assert len(_calls(h, "response_build_clock")) == 1


def test_no_duplicate_upstream_or_boundary_calls(monkeypatch):
    h = _install(monkeypatch)
    _run(h)
    for name in (
        "shadow", "canary", "3z2a", "cp11", "cp12", "cp15",
        "plan_shadow_observability", "release_observability",
        "response_build_clock",
    ):
        assert len(_calls(h, name)) == 1


def test_ast_exact_future_post_cp15_stage_boundary():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_orchestrator"
    )
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]

    def named(name):
        return [node for node in calls if isinstance(node.func, ast.Name)
                and node.func.id == name]

    cp15 = named("run_cp15_release_observer_stage")
    first = named("_record_task_execution_plan_shadow_observability")
    second = named("_record_public_composition_canary_release_observability")
    assert tuple(map(len, (cp15, first, second))) == (1, 1, 1)
    clocks = [
        node for node in function.body if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "response_build_started"
                for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_observability_now"
    ]
    assert len(clocks) == 1
    assert cp15[0].lineno < first[0].lineno < second[0].lineno < clocks[0].lineno

    zones = []
    for call in (first[0], second[0]):
        zone = next(node for node in function.body
                    if isinstance(node, ast.Try) and call in ast.walk(node))
        zones.append(zone)
        assert len(zone.body) == 1 and isinstance(zone.body[0], ast.Expr)
        assert zone.body[0].value is call
        assert [ast.unparse(arg) for arg in call.args] == [
            "counts", "plan", "evidence_pipeline"
        ]
        assert call.keywords == []
        assert len(zone.handlers) == 1
        handler = zone.handlers[0]
        assert ast.unparse(handler.type) == "Exception"
        assert handler.name is None
        assert len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)
        assert zone.orelse == [] and zone.finalbody == []
    assert zones[0] is not zones[1]
    positions = [function.body.index(node) for node in (*zones, clocks[0])]
    assert positions[0] < positions[1] < positions[2]
