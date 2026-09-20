"""Characterize the final public response-build boundary, stopping at total."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class StopAtTotal(BaseException):
    pass


class Fatal(BaseException):
    pass


_DEFAULT = object()


class DictSubclass(dict):
    pass


class TruthProbe:
    def __init__(self, value=True, error=None, events=None, label="truth"):
        self.value = value
        self.error = error
        self.calls = 0
        self.events = [] if events is None else events
        self.label = label

    def __bool__(self):
        self.calls += 1
        self.events.append(self.label)
        if self.error is not None:
            raise self.error
        return self.value


class ProfileValue:
    def __init__(self, debug):
        self.debug = debug

    def __eq__(self, other):
        assert other == "debug"
        return self.debug


class PayloadProxy:
    def __init__(self, wrapped, include_trace, debug, events):
        object.__setattr__(self, "wrapped", wrapped)
        object.__setattr__(self, "include_trace_value", include_trace)
        object.__setattr__(self, "include_trace_calls", 0)
        object.__setattr__(self, "profile", ProfileValue(debug))
        object.__setattr__(self, "events", events)

    def __getattr__(self, name):
        if name == "response_profile":
            return self.profile
        if name == "include_trace":
            object.__setattr__(
                self, "include_trace_calls", self.include_trace_calls + 1
            )
            self.events.append("include_trace")
            return self.include_trace_value
        return getattr(self.wrapped, name)


class RequestedInformationProbe:
    def __init__(self, value, events, error=None):
        self.value = value
        self.events = events
        self.error = error
        self.calls = 0

    @property
    def requested_information(self):
        self.calls += 1
        self.events.append("requested_information")
        if self.error is not None:
            raise self.error
        return self.value


class PlanProxy:
    def __init__(self, wrapped, events, value=_DEFAULT, error=None):
        self.wrapped = wrapped
        self.events = events
        self.value = value
        self.error = error
        self.calls = 0

    def __getattr__(self, name):
        if name != "requested_information" or "response_clock" not in self.events:
            return getattr(self.wrapped, name)
        self.calls += 1
        self.events.append("requested_information")
        if self.error is not None:
            raise self.error
        if self.value is _DEFAULT:
            return self.wrapped.requested_information
        return self.value


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_post_cp15_observability_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("post_cp15_3aa1_for_3ab1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=dict,
    include_trace=False,
    debug=False,
    start_error=None,
    elapsed_error=None,
    evidence_compact_return=_DEFAULT,
    evidence_compact_error=None,
    results_compact_return=_DEFAULT,
    results_compact_error=None,
    model_plan_return=_DEFAULT,
    model_trace_return=_DEFAULT,
    model_error=None,
    trace_model_error=None,
    requested_information=_DEFAULT,
    requested_error=None,
):
    prior = _prior_characterization()
    h = prior._install(monkeypatch, pipeline_factory=pipeline_factory)
    calls, events = h.calls, h.events
    original_plan = h.plan
    h.payload = PayloadProxy(h.payload, include_trace, debug, events)
    h.plan = PlanProxy(original_plan, events, requested_information, requested_error)
    monkeypatch.setattr(service, "run_initial_planning_stage", lambda *a, **k: h.plan)
    original_initial_execution = service.run_initial_execution_stage

    def initial_execution(*args, **kwargs):
        result = original_initial_execution(*args, **kwargs)
        result.plan = h.plan
        return result

    monkeypatch.setattr(service, "run_initial_execution_stage", initial_execution)
    h.cp11_debug = debug
    response_token = object()
    stop = StopAtTotal("controlled total-timing boundary")
    evidence_value = object() if evidence_compact_return is _DEFAULT else evidence_compact_return
    results_value = object() if results_compact_return is _DEFAULT else results_compact_return
    plan_value = object() if model_plan_return is _DEFAULT else model_plan_return
    trace_value = object() if model_trace_return is _DEFAULT else model_trace_return
    response_clock_seen = False
    response_elapsed_seen = False
    boundary_before = {}

    def clock():
        nonlocal response_clock_seen
        if prior._calls(h, "release_observability"):
            events.append("response_clock")
            calls.append(("response_clock", (), {}))
            response_clock_seen = True
            boundary_before.update(
                plan=dict(vars(h.plan.wrapped)), results=list(h.results),
                trace=dict(h.trace), pipeline=(dict(h.pipeline)
                                                if isinstance(h.pipeline, dict)
                                                else h.pipeline),
            )
            if start_error is not None:
                raise start_error
            return response_token
        return 1.0

    def elapsed(started):
        nonlocal response_elapsed_seen
        if started is response_token:
            events.append("response_elapsed")
            calls.append(("elapsed", (started,), {}))
            response_elapsed_seen = True
            if elapsed_error is not None:
                raise elapsed_error
            return 12.5
        if response_elapsed_seen:
            events.append("total_elapsed")
            calls.append(("elapsed", (started,), {}))
            raise stop
        return 0.25

    def compact_evidence(value):
        events.append("compact_evidence")
        calls.append(("compact_evidence", (value,), {}))
        if evidence_compact_error is not None:
            raise evidence_compact_error
        return evidence_value

    def compact_results(value, *, requested_information):
        events.append("compact_results")
        calls.append(("compact_results", (value,),
                      {"requested_information": requested_information}))
        if results_compact_error is not None:
            raise results_compact_error
        return results_value

    def model(value):
        label = "model_plan" if value is h.plan else "model_trace"
        events.append(label)
        calls.append(("model", (value,), {}))
        if model_error is not None:
            raise model_error
        if value is h.trace and trace_model_error is not None:
            raise trace_model_error
        return plan_value if value is h.plan else trace_value

    monkeypatch.setattr(service, "_observability_now", clock)
    monkeypatch.setattr(service, "_observability_elapsed_ms", elapsed)
    monkeypatch.setattr(service, "_compact_evidence_pipeline_for_public_response", compact_evidence)
    monkeypatch.setattr(service, "compact_results_for_public_response", compact_results)
    monkeypatch.setattr(service, "_model_to_dict", model)
    namespace = dict(vars(h))
    namespace.update(locals())
    return SimpleNamespace(**namespace)


def _run(h, exception=StopAtTotal):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    candidate = None
    while traceback is not None:
        local = traceback.tb_frame.f_locals
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            candidate = local
        if traceback.tb_frame.f_code.co_filename.endswith(
            "final_response_build_stage.py"
        ) and "response_build_started" in local:
            candidate = local
        traceback = traceback.tb_next
    if candidate is None:
        raise AssertionError("response-build service frame absent")
    return candidate


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


def test_success_exact_order_identity_response_shape_and_total_stop(monkeypatch):
    h = _install(monkeypatch, model_plan_return=object(), model_trace_return=object())
    local = _locals(_run(h))
    response = local["response"]
    assert list(response) == [
        "status", "answer", "context_type", "question", "query_plan", "research",
        "clarification", "results", "evidence_pipeline", "task_execution_shadow",
        "task_planner_canary", "trace",
    ]
    assert response["context_type"] == "orchestrator"
    for key, local_name in (
        ("status", "status"), ("answer", "answer"), ("question", "question"),
        ("research", "research"), ("clarification", "clarification"),
        ("task_execution_shadow", "task_execution_shadow"),
        ("task_planner_canary", "task_planner_canary"),
    ):
        assert response[key] is local[local_name]
    assert response["query_plan"] is h.plan_value
    assert response["results"] is h.results_value
    assert response["evidence_pipeline"] is h.evidence_value
    assert response["trace"] is None and "observability" not in response
    assert local["timings"]["response_build"] == 12.5
    assert h.payload.include_trace_calls == 3
    assert h.events.index("release_observability") < h.events.index("response_clock")
    assert h.events.index("compact_evidence") < h.events.index("compact_results")
    assert h.events.index("compact_results") < h.events.index("model_plan")
    assert h.events.index("model_plan") < h.events.index("response_elapsed")
    assert h.events.index("response_elapsed") < h.events.index("total_elapsed")
    assert [c[1][0] for c in _calls(h, "elapsed")][-2:] == [h.response_token, local["run_started"]]


@pytest.mark.parametrize("error", [RuntimeError("clock"), Fatal("clock")])
def test_response_clock_error_propagates_before_try_and_elapsed(error, monkeypatch):
    h = _install(monkeypatch, start_error=error)
    assert _run(h, type(error)) is error
    assert len(_calls(h, "response_clock")) == 1
    assert not _calls(h, "compact_evidence") and not _calls(h, "elapsed")


@pytest.mark.parametrize("error", [RuntimeError("compact"), Fatal("compact")])
def test_try_error_runs_finally_but_never_total(error, monkeypatch):
    h = _install(monkeypatch, evidence_compact_error=error)
    assert _run(h, type(error)) is error
    assert [c[1][0] for c in _calls(h, "elapsed")] == [h.response_token]
    assert h.events[-1] == "response_elapsed"


@pytest.mark.parametrize("original", [RuntimeError("try"), Fatal("try")])
@pytest.mark.parametrize("replacement", [ValueError("elapsed"), Fatal("elapsed")])
def test_elapsed_error_replaces_try_error_and_preserves_prior_timing(
    original, replacement, monkeypatch
):
    h = _install(monkeypatch, evidence_compact_error=original, elapsed_error=replacement)
    # Seed through the inherited timing mapping before response construction.
    error = _run(h, type(replacement))
    assert error is replacement
    local = _locals(error)
    assert local["timings"]["response_build"] == 0
    assert error.__context__ is original
    assert len(_calls(h, "elapsed")) == 1


@pytest.mark.parametrize("factory", [dict, DictSubclass])
def test_truthy_debug_keeps_dict_family_and_same_gate(factory, monkeypatch):
    debug = TruthProbe(True)
    h = _install(monkeypatch, pipeline_factory=factory, debug=debug)
    local = _locals(_run(h))
    assert local["response"]["evidence_pipeline"] is h.pipeline
    assert not _calls(h, "compact_evidence")
    assert debug.calls == 2


@pytest.mark.parametrize("factory", [UserDict, list, object])
def test_truthy_debug_replaces_non_dict_with_exact_fresh_dict(factory, monkeypatch):
    original = factory()
    h = _install(monkeypatch, pipeline_factory=original, debug=True)
    local = _locals(_run(h))
    replacement = local["response"]["evidence_pipeline"]
    assert type(replacement) is dict
    assert list(replacement) == ["task_coverage_gate_cp10"]
    assert replacement["task_coverage_gate_cp10"] is local["task_coverage_gate_cp10"]
    assert replacement is not original


def test_falsey_debug_compacts_once_and_preserves_raw_return(monkeypatch):
    debug = TruthProbe(False)
    returned = object()
    h = _install(monkeypatch, pipeline_factory=list, debug=debug,
                 evidence_compact_return=returned)
    local = _locals(_run(h))
    assert local["response"]["evidence_pipeline"] is returned
    assert _calls(h, "compact_evidence")[0][1][0] is h.pipeline
    assert len(_calls(h, "compact_evidence")) == 1 and debug.calls == 2


@pytest.mark.parametrize("error", [RuntimeError("truth"), Fatal("truth")])
def test_debug_truthiness_error_propagates_through_finally(error, monkeypatch):
    debug = TruthProbe(error=error)
    h = _install(monkeypatch, debug=debug)
    assert _run(h, type(error)) is error
    assert debug.calls == 1
    assert [c[1][0] for c in _calls(h, "elapsed")] == [h.response_token]


def test_include_trace_short_circuits_compactors_requested_information(monkeypatch):
    include = TruthProbe(True)
    h = _install(monkeypatch, include_trace=include)
    local = _locals(_run(h))
    assert local["response"]["evidence_pipeline"] is h.pipeline
    assert local["response"]["results"] is h.results
    assert not _calls(h, "compact_evidence") and not _calls(h, "compact_results")
    assert include.calls == 3 and h.payload.include_trace_calls == 3
    assert local["response"]["trace"] is h.trace_value
    assert [c[1][0] for c in _calls(h, "model")] == [h.plan, h.trace]


def test_results_property_precedes_one_runtime_helper_and_preserves_identities(monkeypatch):
    requested = object()
    h = _install(monkeypatch, requested_information=requested)
    local = _locals(_run(h))
    call = _calls(h, "compact_results")[0]
    assert call[1][0] is h.results
    assert call[2]["requested_information"] is requested
    assert h.events.index("requested_information") < h.events.index("compact_results")
    assert local["response"]["results"] is h.results_value


@pytest.mark.parametrize("error", [RuntimeError("property"), Fatal("property")])
def test_requested_information_error_prevents_helper_and_runs_finally(error, monkeypatch):
    h = _install(monkeypatch, requested_error=error)
    assert _run(h, type(error)) is error
    assert not _calls(h, "compact_results")
    assert [c[1][0] for c in _calls(h, "elapsed")] == [h.response_token]


@pytest.mark.parametrize("error", [RuntimeError("results"), Fatal("results")])
def test_results_helper_error_keeps_prior_projection_and_runs_finally(error, monkeypatch):
    h = _install(monkeypatch, results_compact_error=error)
    raised = _run(h, type(error))
    local = _locals(raised)
    assert raised is error
    assert local["public_evidence_pipeline"] is h.evidence_value
    assert "public_results" not in local and "response" not in local
    assert len(_calls(h, "compact_evidence")) == 1
    assert len(_calls(h, "compact_results")) == 1
    assert len(_calls(h, "elapsed")) == 1


@pytest.mark.parametrize("error", [RuntimeError("trace"), Fatal("trace")])
def test_trace_serializer_error_preserves_complete_base_response(error, monkeypatch):
    h = _install(monkeypatch, include_trace=True, trace_model_error=error)
    raised = _run(h, type(error))
    local = _locals(raised)
    assert raised is error
    assert list(local["response"]) == [
        "status", "answer", "context_type", "question", "query_plan", "research",
        "clarification", "results", "evidence_pipeline", "task_execution_shadow",
        "task_planner_canary",
    ]
    assert "trace" not in local["response"]
    assert [c[1][0] for c in _calls(h, "model")] == [h.plan, h.trace]
    assert len(_calls(h, "elapsed")) == 1


@pytest.mark.parametrize("error", [RuntimeError("model"), Fatal("model")])
def test_plan_serializer_error_runs_finally_before_response_binding(error, monkeypatch):
    h = _install(monkeypatch, model_error=error)
    raised = _run(h, type(error))
    local = _locals(raised)
    assert raised is error and "response" not in local
    assert [c[1][0] for c in _calls(h, "model")] == [h.plan]
    assert len(_calls(h, "elapsed")) == 1


def test_total_sentinel_does_not_repeat_any_response_work(monkeypatch):
    h = _install(monkeypatch)
    _run(h)
    assert len(_calls(h, "response_clock")) == 1
    assert len(_calls(h, "compact_evidence")) == 1
    assert len(_calls(h, "compact_results")) == 1
    assert len(_calls(h, "model")) == 1
    assert len(_calls(h, "elapsed")) == 2
    for name in ("shadow", "canary", "3z2a", "cp11", "cp12", "cp15",
                 "plan_shadow_observability", "release_observability"):
        assert len(_calls(h, name)) == 1


def test_fresh_response_and_no_input_mutation_across_core_calls(monkeypatch):
    responses = []
    snapshots = []
    for _ in range(2):
        h = _install(monkeypatch)
        local = _locals(_run(h))
        responses.append(local["response"])
        snapshots.append((h.boundary_before, {
            "plan": dict(vars(h.plan.wrapped)), "results": list(h.results),
            "trace": dict(h.trace), "pipeline": dict(h.pipeline),
        }))
    assert responses[0] is not responses[1]
    assert all(before == after for before, after in snapshots)


def test_ast_exact_future_3ab2_boundary_inputs_outputs_and_total_stop():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "run_orchestrator")
    body = function.body

    def calls_named(name):
        return [n for n in ast.walk(function) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == name]

    post = calls_named("run_post_cp15_observability_stage")
    stage = calls_named("run_final_response_build_stage")
    assert tuple(map(len, (post, stage))) == (1, 1)
    total = next(n for n in body if isinstance(n, ast.Assign)
                 and ast.unparse(n.targets[0]) == "timings['total']")
    statement = next(n for n in body if stage[0] in ast.walk(n))
    binding = next(n for n in body if isinstance(n, ast.Assign)
                   and ast.unparse(n.targets[0]) == "response")
    assert post[0].lineno < stage[0].lineno < binding.lineno < total.lineno
    assert ast.unparse(statement.targets[0]) == "final_response_build_stage_result"
    assert [ast.unparse(arg) for arg in stage[0].args] == [
        "payload", "cp11_debug_response", "evidence_pipeline",
        "task_coverage_gate_cp10", "results", "plan", "status", "answer",
        "question", "research", "clarification", "task_execution_shadow",
        "task_planner_canary", "trace", "timings",
    ]
    assert [(kw.arg, ast.unparse(kw.value)) for kw in stage[0].keywords] == [
        ("observability_now", "_observability_now"),
        ("compact_evidence_pipeline_for_public_response",
         "_compact_evidence_pipeline_for_public_response"),
        ("compact_results_for_public_response", "compact_results_for_public_response"),
        ("model_to_dict", "_model_to_dict"),
        ("observability_elapsed_ms", "_observability_elapsed_ms"),
    ]
    assert ast.unparse(binding.value) == "final_response_build_stage_result.response"
    assert ast.unparse(total.value) == "_observability_elapsed_ms(run_started)"
