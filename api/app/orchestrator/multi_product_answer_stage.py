"""Bounded multi-product answer delegation for the product branch."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MultiProductAnswerStageResult:
    delegated_answer: Any


def run_multi_product_answer_stage(
    results: list[dict[str, Any]],
    requested_information: set[str],
    build_multi_product_user_answer: Callable[
        [list[dict[str, Any]], set[str]],
        Any,
    ],
) -> MultiProductAnswerStageResult:
    return MultiProductAnswerStageResult(
        delegated_answer=build_multi_product_user_answer(
            results,
            requested_information,
        )
    )


__all__ = [
    "MultiProductAnswerStageResult",
    "run_multi_product_answer_stage",
]
