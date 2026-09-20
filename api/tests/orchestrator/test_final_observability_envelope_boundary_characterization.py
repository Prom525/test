"""Characterize the core final-observability envelope boundary after 3AB2."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    pass


class RecordingDict(dict):
    def __init__(self, *args, events=None, set_error=None, **kwargs):
        self.events = [] if events is None else events
        self.set_error = set_error
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.events.append(("set", key, value))
        if key == "total" and self.set_error is not None:
            raise self.set_error
        return super().__setitem__(key, value)


class CopyProbe(UserDict):
    def __init__(self, *args, label, events, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.events = events
        self.error = error

    def keys(self):
        self.events.append(self.label + ".keys")
        if self.error is not None:
            raise self.error
        return super().keys()

    def __getitem__(self, key):
        self.events.append(self.label + ".getitem:" + str(key))
        return super().__getitem__(key)


class ResponseProbe(dict):
    def __init__(self, *args, events, error=None, **kwargs):
        self.events = events
        self.error = error
        self.writes = []
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.events.append("response.set:" + str(key))
        self.writes.append((key, value))
        if key == "observability" and self.error is not None:
            raise self.error
        return super().__setitem__(key, value)


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_final_response_build_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("final_response_3ab1_for_3ac1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    timings_factory=None,
    counts_factory=None,
    total=object(),
    elapsed_error=None,
    response_error=None,
    boundary_events=None,
):
    prior = _prior_characterization()
    h = prior._install(monkeypatch)
    events = h.events if boundary_events is None else boundary_events
    if timings_factory is not None:
        monkeypatch.setattr(service, "_new_observability_timings", timings_factory)
    if counts_factory is not None:
        monkeypatch.setattr(service, "_new_observability_counts", counts_factory)

    original_stage = service.run_final_response_build_stage
    response_probe = None

    def stage(*args, **kwargs):
        nonlocal response_probe
        result = original_stage(*args, **kwargs)
        response_probe = ResponseProbe(
            result.response, events=events, error=response_error
        )
        events.append("3ab2.return")
        return SimpleNamespace(response=response_probe)

    monkeypatch.setattr(service, "run_final_response_build_stage", stage)
    elapsed_calls = []
    response_elapsed_seen = False

    def elapsed(started):
        nonlocal response_elapsed_seen
        elapsed_calls.append(started)
        if started is h.response_token:
            events.append("response_elapsed")
            response_elapsed_seen = True
            return 12.5
        if response_elapsed_seen:
            events.append("total_elapsed")
            if elapsed_error is not None:
                raise elapsed_error
            return total
        events.append("earlier_elapsed")
        return 0.25

    monkeypatch.setattr(service, "_observability_elapsed_ms", elapsed)
    namespace = dict(vars(h))
    namespace.update(
        events=events, elapsed_calls=elapsed_calls,
        response_probe=lambda: response_probe,
    )
    return SimpleNamespace(**namespace)


def _run(h):
    return service._p4_15cp3c_previous_run_orchestrator(
        h.payload, sender=object()
    )


def _service_locals(error):
    traceback = error.__traceback__
    candidate = None
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            local = traceback.tb_frame.f_locals
            if "counts" in local and "run_started" in local:
                candidate = local
        traceback = traceback.tb_next
    if candidate is None:
        raise AssertionError("core service frame absent")
    return candidate


def test_success_exact_order_raw_total_identity_copies_and_same_response(monkeypatch):
    raw_total = object()
    timing_value = object()
    count_value = object()
    events = []

    def timings_factory():
        return RecordingDict({"seed_timing": timing_value}, events=events)

    def counts_factory():
        return CopyProbe({"seed_count": count_value}, label="counts", events=events)

    h = _install(
        monkeypatch, timings_factory=timings_factory,
        counts_factory=counts_factory, total=raw_total, boundary_events=events,
    )
    response = _run(h)
    probe = h.response_probe()
    envelope = response["observability"]

    assert response is probe
    assert h.elapsed_calls[-1] is not h.response_token
    assert envelope["contract_version"] is service.ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION
    assert list(envelope) == ["contract_version", "timings_ms", "counts"]
    assert type(envelope["timings_ms"]) is type(envelope["counts"]) is dict
    assert envelope["timings_ms"]["total"] is raw_total
    assert envelope["timings_ms"]["seed_timing"] is timing_value
    assert envelope["timings_ms"]["response_build"] == 12.5
    assert envelope["counts"]["seed_count"] is count_value
    assert h.events.index("3ab2.return") < h.events.index("total_elapsed")
    assert events.index(("set", "total", raw_total)) < events.index("counts.keys")
    assert events.index("counts.keys") < events.index("response.set:observability")
    assert probe.writes == [("observability", envelope)]
    assert list(response)[-1] == "observability"


def test_copies_are_isolated_shallow_and_fresh_per_core_call(monkeypatch):
    shared = object()
    envelopes = []
    originals = []
    for _ in range(2):
        h = _install(
            monkeypatch,
            timings_factory=lambda: RecordingDict({"nested": shared}),
            counts_factory=lambda: CopyProbe(
                {"nested": shared}, label="counts", events=[]
            ),
            total=1,
        )
        response = _run(h)
        envelope = response["observability"]
        envelopes.append(envelope)
        originals.append((h.response_probe(), envelope["timings_ms"], envelope["counts"]))
        assert envelope["timings_ms"]["nested"] is shared
        assert envelope["counts"]["nested"] is shared
    assert envelopes[0] is not envelopes[1]
    assert originals[0][1] is not originals[1][1]
    assert originals[0][2] is not originals[1][2]


@pytest.mark.parametrize("error", [RuntimeError("elapsed"), Fatal("elapsed")])
def test_total_elapsed_failure_propagates_before_assignment_and_envelope(error, monkeypatch):
    timings = RecordingDict({"before": 1})
    h = _install(monkeypatch, timings_factory=lambda: timings, elapsed_error=error)
    with pytest.raises(type(error)) as raised:
        _run(h)
    assert raised.value is error
    local = _service_locals(error)
    assert h.elapsed_calls[-1] is local["run_started"]
    assert "total" not in timings
    assert "observability" not in h.response_probe()


@pytest.mark.parametrize("error", [RuntimeError("set"), Fatal("set")])
def test_total_setitem_failure_propagates_with_exact_partial_state(error, monkeypatch):
    timings = RecordingDict({"before": 1}, set_error=error)
    counts = CopyProbe({"count": 2}, label="counts", events=[])
    h = _install(
        monkeypatch, timings_factory=lambda: timings,
        counts_factory=lambda: counts, total="raw",
    )
    with pytest.raises(type(error)) as raised:
        _run(h)
    assert raised.value is error
    assert timings == {"before": 1, "presentation": 0.25, "response_build": 12.5}
    assert [event for event in timings.events if event[0] == "set"][-1] == (
        "set", "total", "raw"
    )
    assert counts.events == []
    assert "observability" not in h.response_probe()


@pytest.mark.parametrize("error", [RuntimeError("timings-copy"), Fatal("timings-copy")])
def test_timings_copy_failure_stops_counts_copy_and_response_write(error, monkeypatch):
    events = []
    timings = CopyProbe({"t": 1}, label="timings", events=events, error=error)
    counts = CopyProbe({"c": 2}, label="counts", events=events)
    h = _install(
        monkeypatch, timings_factory=lambda: timings,
        counts_factory=lambda: counts, total=3,
    )
    with pytest.raises(type(error)) as raised:
        _run(h)
    assert raised.value is error
    assert events[-1] == "timings.keys"
    assert not any(event.startswith("counts.") for event in events if isinstance(event, str))
    assert not h.response_probe().writes


@pytest.mark.parametrize("error", [RuntimeError("counts-copy"), Fatal("counts-copy")])
def test_counts_copy_failure_occurs_after_complete_timings_copy_before_write(error, monkeypatch):
    events = []
    timings = CopyProbe({"t": object()}, label="timings", events=events)
    counts = CopyProbe({"c": 2}, label="counts", events=events, error=error)
    h = _install(
        monkeypatch, timings_factory=lambda: timings,
        counts_factory=lambda: counts, total=3,
    )
    with pytest.raises(type(error)) as raised:
        _run(h)
    assert raised.value is error
    assert events.index("timings.keys") < events.index("counts.keys")
    assert any(event.startswith("timings.getitem:") for event in events)
    assert not h.response_probe().writes


@pytest.mark.parametrize("error", [RuntimeError("response-write"), Fatal("response-write")])
def test_response_write_failure_has_one_attempt_no_return_and_keeps_total(error, monkeypatch):
    timings = RecordingDict()
    raw_total = object()
    h = _install(
        monkeypatch, timings_factory=lambda: timings,
        total=raw_total, response_error=error,
    )
    with pytest.raises(type(error)) as raised:
        _run(h)
    assert raised.value is error
    probe = h.response_probe()
    assert len(probe.writes) == 1 and probe.writes[0][0] == "observability"
    assert "observability" not in probe
    assert timings["total"] is raw_total


def test_originals_and_envelope_copies_do_not_mutate_each_other(monkeypatch):
    timings = RecordingDict({"t": 1})
    counts = CopyProbe({"c": 2}, label="counts", events=[])
    h = _install(
        monkeypatch, timings_factory=lambda: timings,
        counts_factory=lambda: counts, total=3,
    )
    envelope = _run(h)["observability"]
    timings["later"] = 4
    counts["later"] = 5
    envelope["timings_ms"]["copy_only"] = 6
    envelope["counts"]["copy_only"] = 7
    assert "later" not in envelope["timings_ms"]
    assert "later" not in envelope["counts"]
    assert "copy_only" not in timings and "copy_only" not in counts


def test_boundary_mutates_only_timings_and_response(monkeypatch):
    h = _install(monkeypatch, total=3)
    _run(h)
    after = {
        "plan": dict(vars(h.plan.wrapped)), "results": list(h.results),
        "trace": dict(h.trace), "pipeline": dict(h.pipeline),
    }
    assert after == h.boundary_before


def test_ast_exact_3ac2_boundary():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_orchestrator"
    )
    body = function.body
    stage_calls = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "run_final_response_build_stage"
    ]
    envelope_calls = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "run_final_observability_envelope_stage"
    ]
    returns = [
        node for node in body if isinstance(node, ast.Return)
        and ast.unparse(node.value) == "response"
    ]
    assert tuple(map(len, (stage_calls, envelope_calls, returns))) == (1, 1, 1)
    response_bindings = [
        node for node in body if isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "response"
    ]
    assert ast.unparse(response_bindings[-2].value) == "final_response_build_stage_result.response"
    assert ast.unparse(response_bindings[-1].value) == "final_observability_envelope_stage_result.response"
    assert stage_calls[0].lineno < response_bindings[-2].lineno < envelope_calls[0].lineno < response_bindings[-1].lineno < returns[0].lineno
    assert [ast.unparse(arg) for arg in envelope_calls[0].args] == [
        "response", "timings", "counts", "run_started",
        "ORCHESTRATOR_OBSERVABILITY_CONTRACT_VERSION",
    ]
    assert [(keyword.arg, ast.unparse(keyword.value))
            for keyword in envelope_calls[0].keywords] == [
        ("observability_elapsed_ms", "_observability_elapsed_ms")]
