"""Characterize the Phase-C evidence-pipeline assembly boundary after 3T2."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.orchestrator import service
from app.orchestrator.phase_c_entry_stage import PhaseCEntryResult
from app.orchestrator.phase_c_synthesis_stage import PhaseCSynthesisStageResult


KEYS = (
    "requirement_set_id",
    "task_execution_plans_shadow",
    "task_execution_plan_comparison_shadow",
    "task_execution_canary_p4_6b",
    "task_evidence_assessments_shadow",
    "task_evidence_authority_p4_6c",
    "task_research_decisions_shadow",
    "task_research_authority_p4_6d1",
    "task_research_execution_authority_p4_6d2",
    "task_research_evidence_authority_p4_6e1",
    "task_grounded_synthesis_authority_p4_6e2",
    "task_grounded_synthesis_coverage_authority_p4_6e3",
    "task_research_contexts_shadow",
    "task_research_call_guards_shadow",
    "task_research_semantics_cp13",
    "task_research_execution_canary_shadow",
    "task_research_evidence_reassessment_shadow",
    "task_grounded_synthesis_shadow",
    "initial_assessment",
    "research_decision",
    "research_execution",
    "reconciliation",
    "synthesis",
    "product_family_coverage",
    "product_family_recovery",
)


class StopAfterAssembly(BaseException):
    pass


class Fatal(BaseException):
    pass


class RequirementSet:
    def __init__(self, value, error=None):
        self.value = value
        self.error = error
        self.reads = 0

    @property
    def requirement_set_id(self):
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.value


def _prior_characterization():
    path = Path(__file__).with_name(
        "test_phase_c_synthesis_boundary_characterization.py"
    )
    spec = importlib.util.spec_from_file_location("phase_c_3t1_for_3u1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(monkeypatch, *, serializer_return=None, property_error=None,
             serializer_error=None, stop=True):
    prior = _prior_characterization()
    h = prior._install(monkeypatch)
    requirement_id = object()
    requirement_set = RequirementSet(requirement_id, property_error)
    mapping_calls = []
    events = []
    stage_returns = {}
    synthesis = object()

    monkeypatch.setattr(
        service,
        "prepare_phase_c_entry",
        lambda *_args, **_kwargs: PhaseCEntryResult(
            requirement_set,
            h.base.base.h.retrieved_at,
            (),
            h.base.base.h.working_evidence_items,
        ),
    )
    def synthesis_stage(*_args, **_kwargs):
        events.append("3t2")
        return PhaseCSynthesisStageResult(synthesis)

    monkeypatch.setattr(service, "run_phase_c_synthesis_stage", synthesis_stage)

    observed_fields = {
        "run_initial_execution_stage": (
            "task_execution_plans_shadow",
            "task_execution_plan_comparison_shadow",
            "task_execution_canary_p4_6b",
        ),
        "run_product_family_recovery_stage": (
            "product_family_coverage", "product_family_recovery",
        ),
        "run_task_evidence_stage": (
            "task_evidence_assessments_shadow", "task_evidence_authority_p4_6c",
        ),
        "run_task_research_decision_stage": (
            "task_research_decisions_shadow", "task_research_authority_p4_6d1",
        ),
        "run_task_research_context_stage": (
            "task_research_contexts_shadow", "task_research_call_guards_shadow",
        ),
        "run_cp13_research_semantics_stage": ("task_research_semantics_cp13",),
        "run_p4_6d2_research_execution_stage": (
            "task_research_execution_authority_p4_6d2",
        ),
        "run_p4_6e1_research_evidence_stage": (
            "task_research_evidence_authority_p4_6e1",
        ),
        "run_p4_6e2_grounded_synthesis_stage": (
            "task_grounded_synthesis_authority_p4_6e2",
        ),
        "run_p4_6e3_synthesis_coverage_stage": (
            "task_grounded_synthesis_coverage_authority_p4_6e3",
        ),
        "run_v8_research_execution_canary_stage": (
            "task_research_execution_canary_shadow",
            "task_research_evidence_reassessment_shadow",
            "task_grounded_synthesis_shadow",
        ),
    }
    for name, fields in observed_fields.items():
        original = getattr(service, name)

        def observe(*args, _original=original, _fields=fields, **kwargs):
            result = _original(*args, **kwargs)
            for field in _fields:
                stage_returns[field] = getattr(result, field)
            return result

        monkeypatch.setattr(service, name, observe)

    def serializer(*args, **kwargs):
        events.append("pipeline")
        mapping_calls.append((args, kwargs))
        if serializer_error is not None:
            raise serializer_error
        if stop:
            raise StopAfterAssembly("controlled following boundary")
        return serializer_return

    monkeypatch.setattr(service, "_evidence_pipeline_to_dict", serializer)
    before = (
        dict(vars(h.base.base.h.plan)),
        list(h.base.base.h.results),
        list(h.base.base.h.typed_results),
        dict(h.base.base.h.trace),
        tuple(h.base.base.h.working_evidence_items),
    )
    base = h
    return SimpleNamespace(**locals())


def _run(h, exception=StopAfterAssembly):
    return h.prior._run(h.base, exception)


def _service_locals(error):
    traceback = error.__traceback__
    while traceback is not None:
        if traceback.tb_frame.f_code is service._p4_15cp3c_previous_run_orchestrator.__code__:
            return traceback.tb_frame.f_locals
        traceback = traceback.tb_next
    raise AssertionError("service frame absent from boundary traceback")


def _expected(h):
    expected = dict(h.stage_returns)
    expected.update({
        "initial_assessment": h.base.base.initial_assessment,
        "research_decision": h.base.base.base.decision,
        "research_execution": h.base.base.research_execution,
        "reconciliation": h.base.reconciliation,
        "synthesis": h.synthesis,
    })
    return expected


def test_single_runtime_serializer_call_exact_plain_ordered_mapping_and_identities(
        monkeypatch):
    h = _install(monkeypatch, stop=False)
    boundary = StopAfterAssembly("controlled following boundary")

    def following_boundary(*_args, **_kwargs):
        h.events.append("following_boundary")
        raise boundary

    monkeypatch.setattr(service, "_build_user_answer", following_boundary)
    raised = _run(h)

    assert raised is boundary
    assert h.events == ["3t2", "pipeline", "following_boundary"]
    assert len(h.mapping_calls) == 1
    args, kwargs = h.mapping_calls[0]
    assert len(args) == 1 and kwargs == {}
    mapping = args[0]
    assert type(mapping) is dict
    assert len(mapping) == 25
    assert tuple(mapping) == KEYS
    assert mapping["requirement_set_id"] is h.requirement_id
    expected = _expected(h)
    assert set(expected) == set(KEYS[1:])
    assert all(mapping[key] is expected[key] for key in KEYS[1:])
    assert h.requirement_set.reads == 1
    assert service._evidence_pipeline_to_dict is h.serializer


@pytest.mark.parametrize("returned", [{"raw": object()}, [object()],
                                      (object(),), None, object()])
def test_serializer_return_is_used_raw_as_evidence_pipeline(monkeypatch, returned):
    h = _install(monkeypatch, serializer_return=returned, stop=False)
    boundary = StopAfterAssembly("controlled legacy presentation boundary")
    monkeypatch.setattr(
        service,
        "_build_user_answer",
        lambda *_a, **_k: (_ for _ in ()).throw(boundary),
    )
    raised = _run(h)
    assert raised is boundary
    assert len(h.mapping_calls) == 1
    assert _service_locals(raised)["evidence_pipeline"] is returned


@pytest.mark.parametrize("where", ["property", "serializer"])
def test_ordinary_failure_uses_outer_fail_open_and_reaches_legacy(monkeypatch, where):
    error = RuntimeError(where)
    h = _install(
        monkeypatch,
        property_error=error if where == "property" else None,
        serializer_error=error if where == "serializer" else None,
    )
    raised = _run(h, h.base.base.base.characterized.StopOnLegacyPath)
    assert isinstance(raised, h.base.base.base.characterized.StopOnLegacyPath)
    assert _service_locals(raised)["evidence_pipeline"] is None
    assert h.requirement_set.reads == 1
    assert len(h.mapping_calls) == (0 if where == "property" else 1)
    assert [row[0] for row in h.base.base.base.h.calls].count("legacy_path") == 1


@pytest.mark.parametrize("where", ["property", "serializer"])
def test_baseexception_propagates_identically(monkeypatch, where):
    error = Fatal(where)
    h = _install(
        monkeypatch,
        property_error=error if where == "property" else None,
        serializer_error=error if where == "serializer" else None,
    )
    raised = _run(h, Fatal)
    assert raised is error
    assert h.requirement_set.reads == 1
    assert len(h.mapping_calls) == (0 if where == "property" else 1)
    assert "legacy_path" not in [row[0] for row in h.base.base.base.h.calls]


def test_following_boundary_failure_does_not_repeat_assembly(monkeypatch):
    h = _install(monkeypatch, serializer_return=object(), stop=False)
    error = RuntimeError("controlled following boundary")
    monkeypatch.setattr(
        service,
        "_build_user_answer",
        lambda *_a, **_k: (_ for _ in ()).throw(error),
    )
    raised = _run(h, RuntimeError)
    assert raised is error
    assert len(h.mapping_calls) == 1
    assert h.requirement_set.reads == 1


def test_fresh_mapping_per_core_call_no_leakage_duplicates_or_input_mutation(
        monkeypatch):
    mappings = []
    snapshots = []
    befores = []
    upstream_counts = []
    for _ in range(2):
        with monkeypatch.context() as patch:
            h = _install(patch)
            _run(h)
            mappings.append(h.mapping_calls[0][0][0])
            snapshots.append((
                dict(vars(h.base.base.base.h.plan)), h.base.base.base.h.results,
                h.base.base.base.h.typed_results, h.base.base.base.h.trace,
                tuple(h.base.base.base.h.working_evidence_items),
            ))
            befores.append(h.before)
            names = [row[0] for row in h.base.base.base.h.calls]
            upstream_counts.append({name: names.count(name) for name in names})

    assert mappings[0] is not mappings[1]
    assert snapshots == befores
    assert all(all(count == 1 for count in counts.values())
               for counts in upstream_counts)
