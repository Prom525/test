"""Single-family product presentation after multi-product delegation declines."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SingleFamilyProductAnswerStageResult:
    answer: str | None


def run_single_family_product_answer_stage(
    specialist_result: dict[str, Any],
    requested_information: set[str],
    *,
    build_product_article_lines: Callable[..., Any],
) -> SingleFamilyProductAnswerStageResult:
    family_context = specialist_result.get("family_context")

    if isinstance(family_context, dict):
        family_rows = family_context.get("results")

        if (
            isinstance(family_rows, list)
            and family_rows
            and isinstance(family_rows[0], dict)
        ):
            family = family_rows[0]

            name = family.get("family_name") or family.get("family_code")
            strengths = family.get("strengths")
            limitations = family.get("limitations")
            selection_advice = family.get("selection_advice")
            answer_lines = []

            if name:
                answer_lines.append(str(name))

            if strengths:
                answer_lines.extend(["", f"Sterktes: {strengths}"])

            if limitations:
                answer_lines.extend(["", f"Beperkingen: {limitations}"])

            if selection_advice:
                answer_lines.extend(["", f"Selectieadvies: {selection_advice}"])

            include_inventory = "inventory" in requested_information
            include_price = "price" in requested_information

            if include_inventory or include_price:
                article_lines = build_product_article_lines(
                    specialist_result,
                    include_inventory=include_inventory,
                    include_price=include_price,
                )

                if article_lines:
                    answer_lines.extend(["", *article_lines])

            if answer_lines:
                return SingleFamilyProductAnswerStageResult(
                    answer="\n".join(answer_lines)
                )

    return SingleFamilyProductAnswerStageResult(answer=None)


__all__ = [
    "SingleFamilyProductAnswerStageResult",
    "run_single_family_product_answer_stage",
]
