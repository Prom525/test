from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class V8ResearchExecutionCanaryStageResult:
    task_research_execution_canary_shadow: Any
    task_research_evidence_reassessment_shadow: Any
    task_grounded_synthesis_shadow: Any


def run_v8_research_execution_canary_stage(
    plan: Any,
    results: Any,
    task_research_contexts_shadow: Any,
    task_research_call_guards_shadow: Any,
    sender: Any,
    working_evidence_items: Any,
    retrieved_at: Any,
    *,
    _run_intent_task_research_execution_canary_shadow: Callable[..., Any],
) -> V8ResearchExecutionCanaryStageResult:
    task_research_execution_canary_shadow = []
    task_research_evidence_reassessment_shadow = []
    task_grounded_synthesis_shadow = []
    try:
        task_research_execution_canary_shadow = (
            _run_intent_task_research_execution_canary_shadow(
                plan,
                list(results),
                task_research_contexts_shadow,
                task_research_call_guards_shadow,
                sender=sender,
                initial_evidence_items=tuple(working_evidence_items),
                reassessment_now=retrieved_at,
                evidence_reassessment_observer=(
                    task_research_evidence_reassessment_shadow.append
                ),
                grounded_synthesis_observer=(
                    task_grounded_synthesis_shadow.append
                ),
            )
        )
    except Exception:
        task_research_execution_canary_shadow = []
        task_research_evidence_reassessment_shadow = []
        task_grounded_synthesis_shadow = []

    return V8ResearchExecutionCanaryStageResult(
        task_research_execution_canary_shadow,
        task_research_evidence_reassessment_shadow,
        task_grounded_synthesis_shadow,
    )
