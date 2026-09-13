"""Pure JSON-safe serialization helpers for the orchestrator."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


def _model_to_dict(model) -> dict[str, Any]:
    """
    Compatibel met Pydantic v1 en v2.
    Geeft JSON-veilige waarden terug, dus ook Enum -> string.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    return json.loads(model.json())


def _evidence_pipeline_to_dict(value: Any) -> Any:
    """Return a detached, JSON-safe representation."""
    if is_dataclass(value):
        return _evidence_pipeline_to_dict(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): _evidence_pipeline_to_dict(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]

    if isinstance(value, (set, frozenset)):
        converted_items = [
            _evidence_pipeline_to_dict(item)
            for item in value
        ]
        return sorted(
            converted_items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        )

    if isinstance(value, datetime):
        return value.isoformat()

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return None


__all__ = (
    "_model_to_dict",
    "_evidence_pipeline_to_dict",
)
