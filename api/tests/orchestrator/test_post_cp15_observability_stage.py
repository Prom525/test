import pytest

from app.orchestrator.post_cp15_observability_stage import (
    run_post_cp15_observability_stage,
)


class Fatal(BaseException):
    pass


def run(first, second, counts=None, plan=None, pipeline=None):
    counts = {} if counts is None else counts
    plan = object() if plan is None else plan
    pipeline = object() if pipeline is None else pipeline
    result = run_post_cp15_observability_stage(
        counts,
        plan,
        pipeline,
        record_task_execution_plan_shadow_observability=first,
        record_public_composition_canary_release_observability=second,
    )
    return result, counts, plan, pipeline


def test_exact_none_args_identity_order_and_ignored_returns():
    calls = []
    counts, plan, pipeline = {}, object(), ["non-dict"]

    def first(*args, **kwargs):
        calls.append(("first", args, kwargs))
        return {"ignored": 1}

    def second(*args, **kwargs):
        calls.append(("second", args, kwargs))
        return object()

    result, *_ = run(first, second, counts, plan, pipeline)
    assert result is None
    assert [call[0] for call in calls] == ["first", "second"]
    for _, args, kwargs in calls:
        assert args == (counts, plan, pipeline)
        assert args[0] is counts and args[1] is plan and args[2] is pipeline
        assert kwargs == {}


@pytest.mark.parametrize("failing", ["first", "second", "both"])
def test_independent_exception_zones_partial_mutations_and_shared_identity(failing):
    calls = []
    counts, plan, pipeline = {}, object(), []

    def first(actual_counts, actual_plan, actual_pipeline):
        calls.append(("first", actual_counts, actual_plan, actual_pipeline))
        actual_counts["first_partial"] = True
        actual_pipeline.append("first_partial")
        if failing in {"first", "both"}:
            raise RuntimeError("first")

    def second(actual_counts, actual_plan, actual_pipeline):
        calls.append(("second", actual_counts, actual_plan, actual_pipeline))
        assert actual_counts["first_partial"] is True
        assert actual_pipeline == ["first_partial"]
        actual_counts["second_partial"] = True
        if failing in {"second", "both"}:
            raise ValueError("second")

    result, *_ = run(first, second, counts, plan, pipeline)
    assert result is None and [call[0] for call in calls] == ["first", "second"]
    assert all(call[1] is counts and call[2] is plan and call[3] is pipeline
               for call in calls)
    assert counts == {"first_partial": True, "second_partial": True}


@pytest.mark.parametrize("failing", ["first", "second"])
def test_baseexception_propagates_and_stops_later_calls(failing):
    fatal, calls = Fatal(failing), []

    def first(*args):
        calls.append("first")
        if failing == "first":
            raise fatal

    def second(*args):
        calls.append("second")
        if failing == "second":
            raise fatal

    with pytest.raises(Fatal) as raised:
        run(first, second)
    assert raised.value is fatal
    assert calls == (["first"] if failing == "first" else ["first", "second"])


def test_no_copies_and_fresh_external_state_per_caller():
    identities = []

    def observe(counts, plan, pipeline):
        identities.append((counts, plan, pipeline))

    first = run(observe, observe)
    second = run(observe, observe)
    assert identities[0] == identities[1]
    assert identities[2] == identities[3]
    assert identities[0][0] is first[1] and identities[0][1] is first[2]
    assert identities[0][2] is first[3]
    assert identities[2][0] is second[1] and identities[2][1] is second[2]
    assert identities[2][2] is second[3]
    assert all(one is not two for one, two in zip(identities[0], identities[2]))
