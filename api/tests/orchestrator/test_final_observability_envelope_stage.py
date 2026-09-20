from collections import UserDict
from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.final_observability_envelope_stage import (
    FinalObservabilityEnvelopeStageResult,
    run_final_observability_envelope_stage,
)


class Fatal(BaseException):
    pass


class Probe(dict):
    def __init__(self, *args, events=None, error=None, key=None, **kwargs):
        self.events = [] if events is None else events
        self.error = error
        self.key = key
        self.writes = []
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.events.append(("set", key, value))
        self.writes.append((key, value))
        if key == self.key and self.error is not None:
            raise self.error
        return super().__setitem__(key, value)


class CopyProbe(UserDict):
    def __init__(self, *args, label, events, error=None, **kwargs):
        self.label = label
        self.events = events
        self.error = error
        super().__init__(*args, **kwargs)

    def keys(self):
        self.events.append(self.label + ".keys")
        if self.error is not None:
            raise self.error
        return super().keys()

    def __getitem__(self, key):
        self.events.append(self.label + ".getitem:" + str(key))
        return super().__getitem__(key)


def run(response, timings, counts, started, version, elapsed):
    return run_final_observability_envelope_stage(
        response, timings, counts, started, version,
        observability_elapsed_ms=elapsed,
    )


def test_frozen_single_field_contract():
    result = FinalObservabilityEnvelopeStageResult(response={})
    assert [field.name for field in fields(result)] == ["response"]
    with pytest.raises(FrozenInstanceError):
        result.response = object()


def test_success_exact_order_identity_raw_value_shallow_copies_and_isolation():
    events = []
    nested = object()
    raw = object()
    started = object()
    version = object()
    response = Probe(events=events)
    timings = CopyProbe({"nested": nested}, label="timings", events=events)
    counts = CopyProbe({"nested": nested}, label="counts", events=events)
    elapsed_calls = []

    result = run(
        response, timings, counts, started, version,
        lambda value: elapsed_calls.append(value) or raw,
    )

    envelope = response["observability"]
    assert result.response is response
    assert elapsed_calls == [started]
    assert timings["total"] is raw
    assert list(envelope) == ["contract_version", "timings_ms", "counts"]
    assert envelope["contract_version"] is version
    assert type(envelope["timings_ms"]) is type(envelope["counts"]) is dict
    assert envelope["timings_ms"] is not timings
    assert envelope["counts"] is not counts
    assert envelope["timings_ms"]["nested"] is nested
    assert envelope["counts"]["nested"] is nested
    assert events.index("timings.keys") < events.index("counts.keys")
    assert events.index("counts.keys") < next(
        index for index, event in enumerate(events)
        if isinstance(event, tuple) and event[1] == "observability"
    )
    timings["later"] = 1
    counts["later"] = 2
    envelope["timings_ms"]["copy"] = 3
    envelope["counts"]["copy"] = 4
    assert "later" not in envelope["timings_ms"]
    assert "later" not in envelope["counts"]
    assert "copy" not in timings and "copy" not in counts


def test_fresh_state_per_call():
    first_response = {}
    second_response = {}
    first = run(first_response, {}, {}, 1, 2, lambda value: 3)
    second = run(second_response, {}, {}, 1, 2, lambda value: 3)
    assert first.response is first_response
    assert second.response is second_response
    assert first.response["observability"] is not second.response["observability"]
    assert first.response["observability"]["timings_ms"] is not second.response["observability"]["timings_ms"]
    assert first.response["observability"]["counts"] is not second.response["observability"]["counts"]


@pytest.mark.parametrize("error", [RuntimeError("elapsed"), Fatal("elapsed")])
def test_elapsed_failure_propagates_before_total_and_write(error):
    response = Probe()
    timings = Probe()
    with pytest.raises(type(error)) as raised:
        run(response, timings, {}, object(), object(),
            lambda value: (_ for _ in ()).throw(error))
    assert raised.value is error
    assert timings.writes == []
    assert response.writes == []


@pytest.mark.parametrize("error", [RuntimeError("set"), Fatal("set")])
def test_total_setitem_failure_propagates_before_copies_and_response_write(error):
    events = []
    timings = Probe({"before": 1}, events=events, error=error, key="total")
    counts = CopyProbe({"count": 2}, label="counts", events=events)
    response = Probe(events=events)
    raw = object()
    with pytest.raises(type(error)) as raised:
        run(response, timings, counts, object(), object(), lambda value: raw)
    assert raised.value is error
    assert timings == {"before": 1}
    assert timings.writes == [("total", raw)]
    assert counts.events == events
    assert not any(event == "counts.keys" for event in events)
    assert response.writes == []


@pytest.mark.parametrize("which", ["timings", "counts"])
@pytest.mark.parametrize("error", [RuntimeError("copy"), Fatal("copy")])
def test_copy_failure_evaluation_order_and_propagation(which, error):
    events = []
    timings = CopyProbe({"t": 1}, label="timings", events=events,
                        error=error if which == "timings" else None)
    counts = CopyProbe({"c": 2}, label="counts", events=events,
                       error=error if which == "counts" else None)
    response = Probe(events=events)
    with pytest.raises(type(error)) as raised:
        run(response, timings, counts, object(), object(), lambda value: 3)
    assert raised.value is error
    assert timings["total"] == 3
    assert response.writes == []
    if which == "timings":
        assert "counts.keys" not in events
    else:
        assert events.index("timings.keys") < events.index("counts.keys")


@pytest.mark.parametrize("error", [RuntimeError("write"), Fatal("write")])
def test_response_write_failure_propagates_once_and_keeps_total(error):
    response = Probe(error=error, key="observability")
    timings = {}
    raw = object()
    with pytest.raises(type(error)) as raised:
        run(response, timings, {}, object(), object(), lambda value: raw)
    assert raised.value is error
    assert timings["total"] is raw
    assert len(response.writes) == 1
    assert response.writes[0][0] == "observability"
    assert "observability" not in response
