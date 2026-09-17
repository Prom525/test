from dataclasses import FrozenInstanceError, fields

import pytest

from app.orchestrator.phase_c_evidence_pipeline_stage import (
    PhaseCEvidencePipelineStageResult,
    run_phase_c_evidence_pipeline_stage,
)


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


class Fatal(BaseException):
    pass


def _inputs():
    return {key: object() for key in KEYS[1:]}


def _run(requirement_set, serializer, values=None):
    return run_phase_c_evidence_pipeline_stage(
        requirement_set,
        **(values or _inputs()),
        evidence_pipeline_to_dict=serializer,
    )


def test_result_is_frozen_exact_one_field_contract():
    value = object()
    result = PhaseCEvidencePipelineStageResult(value)
    assert [field.name for field in fields(result)] == ["evidence_pipeline"]
    assert result.evidence_pipeline is value
    with pytest.raises(FrozenInstanceError):
        result.evidence_pipeline = None


@pytest.mark.parametrize("returned", [{"raw": object()}, [], (), None, object()])
def test_exact_plain_ordered_fresh_mapping_identities_and_raw_return(returned):
    requirement_id = object()
    requirement_set = RequirementSet(requirement_id)
    values = _inputs()
    calls = []

    def serializer(*args, **kwargs):
        calls.append((args, kwargs))
        return returned

    result = _run(requirement_set, serializer, values)
    assert result.evidence_pipeline is returned
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert len(args) == 1 and kwargs == {}
    mapping = args[0]
    assert type(mapping) is dict
    assert tuple(mapping) == KEYS
    assert len(mapping) == 25
    assert mapping["requirement_set_id"] is requirement_id
    assert all(mapping[key] is values[key] for key in KEYS[1:])
    assert requirement_set.reads == 1


def test_fresh_mapping_without_input_mutation_or_duplicate_reads():
    requirement_set = RequirementSet(object())
    values = _inputs()
    before = dict(values)
    mappings = []

    def serializer(mapping):
        mappings.append(mapping)
        return mapping

    first = _run(requirement_set, serializer, values)
    second = _run(requirement_set, serializer, values)
    assert mappings[0] is not mappings[1]
    assert first.evidence_pipeline is mappings[0]
    assert second.evidence_pipeline is mappings[1]
    assert values == before
    assert requirement_set.reads == 2


@pytest.mark.parametrize("where", ["property", "serializer"])
@pytest.mark.parametrize("error_type", [RuntimeError, Fatal])
def test_exception_and_baseexception_propagate_unchanged(where, error_type):
    error = error_type(where)
    requirement_set = RequirementSet(
        object(), error if where == "property" else None
    )
    calls = []

    def serializer(mapping):
        calls.append(mapping)
        if where == "serializer":
            raise error
        return object()

    with pytest.raises(error_type) as raised:
        _run(requirement_set, serializer)
    assert raised.value is error
    assert requirement_set.reads == 1
    assert len(calls) == (0 if where == "property" else 1)


def test_all_pipeline_values_and_serializer_are_keyword_only():
    with pytest.raises(TypeError):
        run_phase_c_evidence_pipeline_stage(
            RequirementSet(object()), *list(_inputs().values()), lambda value: value
        )
