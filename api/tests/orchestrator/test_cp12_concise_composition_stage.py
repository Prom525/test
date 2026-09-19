from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.cp12_concise_composition_stage import (
    CP12ConciseCompositionStageResult,
    run_cp12_concise_composition_stage,
)


class Fatal(BaseException):
    pass


def run(returned=("composed", {"public_answer_replaced": True}),
        pipeline=None, authority=None, composer=None):
    pipeline = {} if pipeline is None else pipeline
    authority = {"existing": 1} if authority is None else authority
    composer = composer or (lambda *args, **kwargs: returned)
    return run_cp12_concise_composition_stage(
        "answer", "legacy", "profile", "coverage", "presenter",
        pipeline, authority, compose_concise_public_answer=composer,
    )


def test_frozen_exact_four_field_contract():
    assert [field.name for field in fields(CP12ConciseCompositionStageResult)] == [
        "answer", "evidence_pipeline", "task_concise_composer_cp12",
        "task_public_composition_authority_p4_6f",
    ]
    with pytest.raises(FrozenInstanceError):
        run().answer = "changed"


def test_composer_arguments_and_result_identity():
    values = [object() for _ in range(5)]
    pipeline, authority, answer = {}, {}, object()
    status = {"public_answer_replaced": True}
    calls = []

    def composer(*args, **kwargs):
        calls.append((args, kwargs))
        return answer, status

    result = run_cp12_concise_composition_stage(
        *values, pipeline, authority, compose_concise_public_answer=composer,
    )
    assert calls == [((values[0], values[1]), {
        "response_profile": values[2], "task_coverage_gate_cp10": values[3],
        "task_presenter_cp11": values[4],
    })]
    assert result.answer is answer and result.task_concise_composer_cp12 is status
    assert result.evidence_pipeline is pipeline
    assert result.task_public_composition_authority_p4_6f is authority


@pytest.mark.parametrize("returned", [
    ("a", {"public_answer_replaced": True}),
    ["a", {"public_answer_replaced": True}],
    (value for value in ("a", {"public_answer_replaced": True})),
])
def test_exact_python_two_value_unpacking(returned):
    assert run(returned=returned).answer == "a"


def test_exact_python_dict_unpacking_uses_keys():
    class Status:
        def __getitem__(self, key):
            assert key == "public_answer_replaced"
            return True
    status = Status()
    result = run(returned={"a": 1, status: 2})
    assert result.answer == "a" and result.task_concise_composer_cp12 is status


@pytest.mark.parametrize("returned", [None, (), (1,), (1, 2, 3), 1])
def test_malformed_returns_propagate(returned):
    with pytest.raises((TypeError, ValueError)):
        run(returned=returned)


def test_iterator_failure_propagates():
    def broken():
        yield "a"
        raise RuntimeError("unpack")
    with pytest.raises(RuntimeError, match="unpack"):
        run(returned=broken())


@pytest.mark.parametrize("error", [RuntimeError("composer"), Fatal("composer")])
def test_composer_exception_and_baseexception_propagate(error):
    with pytest.raises(type(error)) as caught:
        run(composer=lambda *args, **kwargs: (_ for _ in ()).throw(error))
    assert caught.value is error


def test_first_write_failure_prevents_status_read_and_authority_update():
    class Pipeline(dict):
        def __setitem__(self, key, value):
            raise RuntimeError("first write")
    class Status:
        def __getitem__(self, key):
            raise AssertionError("status read")
    authority = {"old": 1}
    with pytest.raises(RuntimeError, match="first write"):
        run(returned=("a", Status()), pipeline=Pipeline(), authority=authority)
    assert authority == {"old": 1}


@pytest.mark.parametrize("replacement", [1, "yes", object(), False, None])
def test_only_singleton_true_avoids_rollback(replacement):
    authority = {"old": 1}
    run(returned=("a", {"public_answer_replaced": replacement, "reason": "r"}),
        authority=authority)
    assert authority["blocked"] is True


def test_singleton_true_has_no_truthiness_or_authority_write():
    class Pipeline(dict):
        def __setitem__(self, key, value):
            if key == "task_public_composition_authority_p4_6f":
                raise AssertionError("authority write")
            super().__setitem__(key, value)
    authority = {"unchanged": True}
    result = run(returned=("a", {"public_answer_replaced": True}),
                 pipeline=Pipeline(), authority=authority)
    assert result.task_public_composition_authority_p4_6f is authority
    assert authority == {"unchanged": True}


def test_two_getitem_reads_in_place_update_and_first_write():
    class Status:
        def __init__(self): self.reads = []
        def __getitem__(self, key):
            self.reads.append(key)
            return False if key == "public_answer_replaced" else "reason"
    status, pipeline, authority = Status(), {}, {"old": object()}
    old = authority["old"]
    result = run(returned=("a", status), pipeline=pipeline, authority=authority)
    assert status.reads == ["public_answer_replaced", "reason"]
    assert pipeline["task_concise_composer_cp12"] is status
    assert pipeline["task_public_composition_authority_p4_6f"] is authority
    assert result.evidence_pipeline is pipeline and authority["old"] is old


@pytest.mark.parametrize("missing", ["public_answer_replaced", "reason"])
def test_missing_keys_propagate_after_exact_partial_state(missing):
    status = ({"reason": "r"} if missing == "public_answer_replaced"
              else {"public_answer_replaced": False})
    pipeline, authority = {}, {"old": 1}
    with pytest.raises(KeyError, match=missing):
        run(returned=("a", status), pipeline=pipeline, authority=authority)
    assert pipeline["task_concise_composer_cp12"] is status
    assert authority == {"old": 1}


@pytest.mark.parametrize("error", [RuntimeError("update"), Fatal("update")])
def test_update_errors_preserve_partial_state(error):
    class Authority(dict):
        def update(self, values):
            self["partial"] = values["authoritative"]
            raise error
    pipeline, authority = {}, Authority(old=1)
    with pytest.raises(type(error)) as caught:
        run(returned=("a", {"public_answer_replaced": False, "reason": "r"}),
            pipeline=pipeline, authority=authority)
    assert caught.value is error and authority["partial"] is False
    assert "task_concise_composer_cp12" in pipeline


def test_second_write_failure_keeps_earlier_mutations():
    class Pipeline(dict):
        def __setitem__(self, key, value):
            if key == "task_public_composition_authority_p4_6f":
                raise RuntimeError("second write")
            super().__setitem__(key, value)
    pipeline, authority = Pipeline(), {"old": 1}
    with pytest.raises(RuntimeError, match="second write"):
        run(returned=("a", {"public_answer_replaced": False, "reason": "r"}),
            pipeline=pipeline, authority=authority)
    assert "task_concise_composer_cp12" in pipeline
    assert authority["blocked"] is True


def test_fresh_state_is_owned_by_callers():
    first, second = run(), run()
    assert first.evidence_pipeline is not second.evidence_pipeline
    assert (first.task_public_composition_authority_p4_6f is not
            second.task_public_composition_authority_p4_6f)
