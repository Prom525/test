"""Characterize the service-owned CP12 composition block up to CP15."""
from __future__ import annotations

import ast
import importlib.util
from collections import UserDict
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service


class StopAtCP15(BaseException):
    pass


class StopAfterTypeGate(BaseException):
    pass


class Fatal(BaseException):
    pass


class DictSubclass(dict):
    pass


class PipelineProbe(dict):
    def __init__(self, initial=(), *, fail_key=None, error=None):
        super().__init__(initial)
        self.fail_key = fail_key
        self.error = error
        self.set_calls = []
        self.successful_set_calls = []

    def __setitem__(self, key, value):
        self.set_calls.append((key, value))
        if key == self.fail_key:
            raise self.error
        super().__setitem__(key, value)
        self.successful_set_calls.append((key, value))


class StatusProbe(dict):
    __hash__ = object.__hash__

    def __init__(self, *args, fail_key=None, error=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_key = fail_key
        self.error = error
        self.getitem_calls = []

    def __getitem__(self, key):
        self.getitem_calls.append(key)
        if key == self.fail_key:
            raise self.error
        return super().__getitem__(key)

    def get(self, *args, **kwargs):
        raise AssertionError("CP12 rollback must use __getitem__, not get")


class AuthorityProbe(dict):
    def __init__(self, *args, update_error=None, partial=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_error = update_error
        self.partial = partial
        self.update_calls = []

    def update(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))
        if self.partial:
            mapping = dict(*args, **kwargs)
            first = next(iter(mapping.items()))
            dict.__setitem__(self, *first)
        if self.update_error is not None:
            raise self.update_error
        return super().update(*args, **kwargs)


class IterationFailure:
    def __init__(self, error):
        self.error = error

    def __iter__(self):
        raise self.error


class TruthProbe:
    def __init__(self, value):
        self.value = value
        self.bool_calls = 0

    def __bool__(self):
        self.bool_calls += 1
        return self.value


class PayloadProxy:
    """Delegate all payload fields while scripting response_profile accesses."""

    def __init__(self, wrapped, values):
        object.__setattr__(self, "wrapped", wrapped)
        object.__setattr__(self, "values", iter(values))
        object.__setattr__(self, "profile_calls", 0)

    def __getattr__(self, name):
        if name == "response_profile":
            object.__setattr__(self, "profile_calls", self.profile_calls + 1)
            value = next(self.values)
            if isinstance(value, BaseException):
                raise value
            if value is _MISSING:
                raise AttributeError(name)
            return value
        return getattr(self.wrapped, name)


_DEFAULT = object()
_MISSING = object()


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_cp11_presentation_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("cp11_3z1c_for_3z1d", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(
    monkeypatch,
    *,
    pipeline_factory=PipelineProbe,
    composer_return=_DEFAULT,
    composer_error=None,
    authority=_DEFAULT,
    profile=_DEFAULT,
    cp15_error=_DEFAULT,
):
    prior = _prior_characterization()
    pipeline = pipeline_factory() if callable(pipeline_factory) else pipeline_factory
    authority_value = AuthorityProbe(old=object()) if authority is _DEFAULT else authority
    h = prior._install(
        monkeypatch,
        pipeline_factory=pipeline,
        presenter_return=(object(), object(), authority_value),
    )
    calls, events = h.calls, h.events
    answer_before_cp12 = h.returned[0]
    presenter = h.returned[1]
    if composer_return is _DEFAULT:
        status = StatusProbe(public_answer_replaced=True, reason="unused")
        returned = (object(), status)
    else:
        returned = composer_return
        status = (composer_return[1] if isinstance(composer_return, (tuple, list))
                  and len(composer_return) > 1 else None)
    boundary = StopAtCP15("controlled CP15 stop boundary")
    cp15_failure = boundary if cp15_error is _DEFAULT else cp15_error

    # The service has one earlier debug-profile read. Script that first read and
    # independently characterize the CP12 read that immediately precedes compose.
    if profile is not _DEFAULT:
        h.payload = PayloadProxy(h.payload, [None, profile])

    def composer(*args, **kwargs):
        if isinstance(pipeline, PipelineProbe):
            pipeline.set_calls.clear()
            pipeline.successful_set_calls.clear()
        events.append("cp12")
        calls.append(("cp12", args, kwargs))
        if composer_error is not None:
            raise composer_error
        return returned

    def cp15(*args, **kwargs):
        events.append("cp15")
        calls.append(("cp15", args, kwargs))
        raise cp15_failure

    monkeypatch.setattr(service, "compose_concise_public_answer", composer)
    monkeypatch.setattr(service, "build_release_gate_cp15", cp15)
    before = (dict(vars(h.plan)), list(h.results), list(h.typed), dict(h.trace))
    namespace = dict(vars(h))
    namespace.update(locals())
    namespace.update(plan=h.plan, results=h.results, typed=h.typed,
                     trace=h.trace, payload=h.payload)
    return SimpleNamespace(**namespace)


def _run(h, exception=StopAtCP15):
    with pytest.raises(exception) as raised:
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    return raised.value


def _locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code.co_filename == service.__file__:
            local = traceback.tb_frame.f_locals
            if "cp11_presentation_stage_result" in local:
                return local
        traceback = traceback.tb_next
    raise AssertionError("service frame absent")


def _calls(h, name):
    return [call for call in h.calls if call[0] == name]


@pytest.mark.parametrize("factory", [PipelineProbe, DictSubclass])
def test_dict_gate_accepts_real_dict_family_and_reaches_cp12_cp15(monkeypatch, factory):
    pipeline = factory()
    h = _install(monkeypatch, pipeline_factory=pipeline)
    local = _locals(_run(h))
    assert local["evidence_pipeline"] is pipeline
    assert len(_calls(h, "cp11")) == len(_calls(h, "cp12")) == len(_calls(h, "cp15")) == 1


@pytest.mark.parametrize("factory", [UserDict, list, tuple, lambda: None, object])
def test_dict_gate_rejects_other_types_and_skips_cp11_cp12_cp15(monkeypatch, factory):
    prior = _prior_characterization()
    pipeline = factory()
    h = prior._install(monkeypatch, pipeline_factory=pipeline)
    boundary = StopAfterTypeGate("after gate")

    def after(*args, **kwargs):
        raise boundary

    monkeypatch.setattr(service, "_record_task_execution_plan_shadow_observability", after)
    assert prior._run(h, StopAfterTypeGate) is boundary
    assert not prior._calls(h, "cp11") and not prior._calls(h, "cp12")


@pytest.mark.parametrize("profile", [_MISSING, None, "", "compact", "debug", object()])
def test_response_profile_single_cp12_read_and_exact_composer_call(monkeypatch, profile):
    h = _install(monkeypatch, profile=profile)
    local = _locals(_run(h))
    call = _calls(h, "cp12")[0]
    expected = "compact" if profile is _MISSING else profile
    assert h.payload.profile_calls == 2  # one earlier debug read, exactly one CP12 read
    assert call[1] == (h.answer_before_cp12, h.legacy)
    assert call[1][0] is h.answer_before_cp12
    assert call[2]["response_profile"] is expected
    assert call[2]["task_coverage_gate_cp10"] is h.coverage
    assert call[2]["task_presenter_cp11"] is h.presenter
    assert local["task_concise_composer_cp12"] is h.status


@pytest.mark.parametrize("error", [RuntimeError("profile"), Fatal("profile")])
def test_cp12_profile_errors_propagate_identically_before_composer(monkeypatch, error):
    h = _install(monkeypatch, profile=error)
    assert _run(h, type(error)) is error
    assert not _calls(h, "cp12") and not _calls(h, "cp15")


@pytest.mark.parametrize("error", [RuntimeError("composer"), Fatal("composer")])
def test_composer_errors_propagate_without_fail_open(monkeypatch, error):
    h = _install(monkeypatch, composer_error=error)
    assert _run(h, type(error)) is error
    assert len(_calls(h, "cp12")) == 1 and not _calls(h, "cp15")
    assert "task_concise_composer_cp12" not in h.pipeline


def _two_values():
    yield "generator-answer"
    yield StatusProbe(public_answer_replaced=True)


@pytest.mark.parametrize("returned,expected", [
    (("tuple-answer", StatusProbe(public_answer_replaced=True)), "tuple-answer"),
    (["list-answer", StatusProbe(public_answer_replaced=True)], "list-answer"),
    ({"dict-answer": 1, StatusProbe(public_answer_replaced=True): 2}, "dict-answer"),
    (_two_values(), "generator-answer"),
])
def test_exact_python_two_value_unpacking_success(monkeypatch, returned, expected):
    h = _install(monkeypatch, composer_return=returned)
    local = _locals(_run(h))
    assert local["answer"] == expected
    if isinstance(returned, (tuple, list)):
        assert local["answer"] is returned[0]
        assert local["task_concise_composer_cp12"] is returned[1]


@pytest.mark.parametrize("returned", [None, object(), (), (1,), (1, 2, 3), "x"])
def test_malformed_two_value_unpacking_propagates_without_writes(monkeypatch, returned):
    h = _install(monkeypatch, composer_return=returned)
    _run(h, (TypeError, ValueError))
    assert not _calls(h, "cp15")
    assert "task_concise_composer_cp12" not in h.pipeline


@pytest.mark.parametrize("error", [RuntimeError("iterate"), Fatal("iterate")])
def test_unpack_iterator_errors_propagate_identically(monkeypatch, error):
    h = _install(monkeypatch, composer_return=IterationFailure(error))
    assert _run(h, type(error)) is error
    assert not _calls(h, "cp15") and "task_concise_composer_cp12" not in h.pipeline


@pytest.mark.parametrize("error", [RuntimeError("write"), Fatal("write")])
def test_first_pipeline_write_failure_propagates_once_without_cp15(monkeypatch, error):
    pipeline = PipelineProbe({"preserved": object()}, fail_key="task_concise_composer_cp12", error=error)
    h = _install(monkeypatch, pipeline_factory=pipeline)
    assert _run(h, type(error)) is error
    assert pipeline.set_calls[-1] == ("task_concise_composer_cp12", h.status)
    assert "preserved" in pipeline and "task_concise_composer_cp12" not in pipeline
    assert not _calls(h, "cp15")


@pytest.mark.parametrize("value", [True, False, None, 0, 1])
def test_rollback_uses_identity_with_true_singleton(monkeypatch, value):
    authority = AuthorityProbe(preserved=object())
    status = StatusProbe(public_answer_replaced=value, reason=object())
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    _run(h)
    assert status.getitem_calls == ["public_answer_replaced"] + ([] if value is True else ["reason"])
    assert len(authority.update_calls) == (0 if value is True else 1)
    authority_writes = [x for x in h.pipeline.set_calls if x[0] == "task_public_composition_authority_p4_6f"]
    assert len(authority_writes) == (0 if value is True else 1)


@pytest.mark.parametrize("truth", [True, False])
def test_rollback_does_not_coerce_truthiness(monkeypatch, truth):
    value = TruthProbe(truth)
    authority = AuthorityProbe()
    status = StatusProbe(public_answer_replaced=value, reason="identity comparison")
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    _run(h)
    assert value.bool_calls == 0 and len(authority.update_calls) == 1


def test_status_dict_subclass_and_missing_or_broken_getitem(monkeypatch):
    status = StatusProbe(reason="missing replacement")
    h = _install(monkeypatch, composer_return=(object(), status))
    with pytest.raises(KeyError):
        service._p4_15cp3c_previous_run_orchestrator(h.payload, sender=object())
    assert status.getitem_calls == ["public_answer_replaced"] and not _calls(h, "cp15")


@pytest.mark.parametrize("error", [RuntimeError("getitem"), Fatal("getitem")])
def test_getitem_errors_propagate_identically(monkeypatch, error):
    status = StatusProbe(public_answer_replaced=False, reason="x",
                         fail_key="public_answer_replaced", error=error)
    h = _install(monkeypatch, composer_return=(object(), status))
    assert _run(h, type(error)) is error
    assert status.getitem_calls == ["public_answer_replaced"] and not _calls(h, "cp15")


def test_rollback_updates_same_authority_with_exact_fields_then_second_write(monkeypatch):
    preserved = object()
    reason = object()
    authority = AuthorityProbe(preserved=preserved, authoritative=True)
    status = StatusProbe(public_answer_replaced=False, reason=reason)
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    local = _locals(_run(h))
    assert status.getitem_calls == ["public_answer_replaced", "reason"]
    expected = {"authoritative": False, "public_answer_authority": False,
                "public_answer_replaced": False, "blocked": True, "reason": reason}
    assert authority.update_calls == [((expected,), {})]
    assert authority["preserved"] is preserved and all(authority[k] is v for k, v in expected.items())
    assert local["task_public_composition_authority_p4_6f"] is authority
    assert h.pipeline["task_public_composition_authority_p4_6f"] is authority


@pytest.mark.parametrize("error", [RuntimeError("reason"), Fatal("reason")])
def test_reason_getitem_failure_happens_after_composer_write_before_update(monkeypatch, error):
    authority = AuthorityProbe()
    status = StatusProbe(public_answer_replaced=False, reason="x", fail_key="reason", error=error)
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    assert _run(h, type(error)) is error
    assert h.pipeline["task_concise_composer_cp12"] is status
    assert status.getitem_calls == ["public_answer_replaced", "reason"]
    assert not authority.update_calls and not _calls(h, "cp15")


def test_authority_without_update_propagates_after_composer_write(monkeypatch):
    authority = object()
    status = StatusProbe(public_answer_replaced=False, reason="x")
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    _run(h, AttributeError)
    assert h.pipeline["task_concise_composer_cp12"] is status and not _calls(h, "cp15")


@pytest.mark.parametrize("error", [RuntimeError("update"), Fatal("update")])
@pytest.mark.parametrize("partial", [False, True])
def test_authority_update_failures_preserve_exact_possible_partial_state(monkeypatch, error, partial):
    authority = AuthorityProbe(preserved=object(), update_error=error, partial=partial)
    status = StatusProbe(public_answer_replaced=False, reason="x")
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority)
    assert _run(h, type(error)) is error
    assert h.pipeline["task_concise_composer_cp12"] is status
    assert authority.get("authoritative", _MISSING) is (False if partial else _MISSING)
    assert not _calls(h, "cp15")


@pytest.mark.parametrize("error", [RuntimeError("second write"), Fatal("second write")])
def test_second_pipeline_write_failure_keeps_composer_and_authority_mutations(monkeypatch, error):
    pipeline = PipelineProbe(fail_key="task_public_composition_authority_p4_6f", error=error)
    authority = AuthorityProbe()
    status = StatusProbe(public_answer_replaced=False, reason="blocked")
    h = _install(monkeypatch, pipeline_factory=pipeline,
                 composer_return=(object(), status), authority=authority)
    # CP11's first authority write is also this key, so arm the failure only after compose.
    pipeline.fail_key = None
    original = service.compose_concise_public_answer

    def arm(*args, **kwargs):
        result = original(*args, **kwargs)
        pipeline.fail_key = "task_public_composition_authority_p4_6f"
        return result

    monkeypatch.setattr(service, "compose_concise_public_answer", arm)
    assert _run(h, type(error)) is error
    assert pipeline["task_concise_composer_cp12"] is status
    assert authority["blocked"] is True and not _calls(h, "cp15")


@pytest.mark.parametrize("replacement", [True, False])
def test_cp15_is_exact_stop_after_all_cp12_mutations(monkeypatch, replacement):
    authority = AuthorityProbe()
    status = StatusProbe(public_answer_replaced=replacement, reason="r")
    failure = StopAtCP15("unique")
    h = _install(monkeypatch, composer_return=(object(), status), authority=authority,
                 cp15_error=failure)
    assert _run(h) is failure
    call = _calls(h, "cp15")[0]
    assert call[1][0] is _locals(failure)["task_execution_shadow"]
    assert call[1][1] is h.pipeline and call[2] == {}
    assert h.pipeline["task_concise_composer_cp12"] is status
    assert len(_calls(h, "cp15")) == 1


def test_cardinality_order_fresh_state_and_upstream_immutability(monkeypatch):
    first = _install(monkeypatch)
    _run(first)
    second = _install(monkeypatch)
    _run(second)
    assert first.pipeline is not second.pipeline and first.status is not second.status
    for h in (first, second):
        for name in ("answer", "shadow", "canary", "3z2a", "cp10_authority",
                     "cp10_canary", "cp11", "cp12", "cp15"):
            assert len(_calls(h, name)) == 1
        assert h.events.index("3z2a") < h.events.index("cp11") < h.events.index("cp12") < h.events.index("cp15")
        assert (dict(vars(h.plan)), h.results, h.typed, h.trace) == h.before


def test_ast_cp11_cp12_cp15_single_order_gate_bindings_writes_and_rollback_shape():
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_orchestrator")
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]

    def named(name):
        return [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == name]

    cp11, cp12, cp15 = (named(name) for name in (
        "run_cp11_presentation_stage", "run_cp12_concise_composition_stage",
        "run_cp15_release_observer_stage"))
    assert tuple(map(len, (cp11, cp12, cp15))) == (1, 1, 1)
    assert cp11[0].lineno < cp12[0].lineno < cp15[0].lineno
    gate = next(n for n in function.body if isinstance(n, ast.If) and cp12[0] in ast.walk(n))
    assert ast.dump(gate.test, include_attributes=False) == ast.dump(
        ast.parse("isinstance(evidence_pipeline, dict)", mode="eval").body,
        include_attributes=False,
    )
    profile = next(n for n in gate.body if isinstance(n, ast.Assign)
                   and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == "cp12_response_profile")
    assert profile.lineno < cp12[0].lineno
    assert ast.unparse(profile.value) == "getattr(payload, 'response_profile', 'compact')"
    assert [a.id for a in cp12[0].args] == ["answer",
        "legacy_answer_before_public_composition_canary", "cp12_response_profile",
        "task_coverage_gate_cp10", "task_presenter_cp11", "evidence_pipeline",
        "task_public_composition_authority_p4_6f"]
    assert [(k.arg, k.value.id) for k in cp12[0].keywords] == [
        ("compose_concise_public_answer", "compose_concise_public_answer")]
    bindings = [n for n in gate.body if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Attribute)
                and isinstance(n.value.value, ast.Name)
                and n.value.value.id == "cp12_concise_composition_stage_result"]
    assert [(n.targets[0].id, n.value.attr) for n in bindings] == [
        ("answer", "answer"), ("evidence_pipeline", "evidence_pipeline"),
        ("task_concise_composer_cp12", "task_concise_composer_cp12"),
        ("task_public_composition_authority_p4_6f",
         "task_public_composition_authority_p4_6f")]
