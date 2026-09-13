"""Contracts for the mechanical serialization leaf-module extraction."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path

from app.orchestrator import serialization_stage, service


def test_service_reexports_the_exact_extracted_function_objects():
    for name in serialization_stage.__all__:
        assert getattr(service, name) is getattr(serialization_stage, name)


def test_leaf_module_has_exact_surface_and_only_minimal_imports():
    assert serialization_stage.__all__ == (
        "_model_to_dict",
        "_evidence_pipeline_to_dict",
    )
    tree = ast.parse(
        Path(serialization_stage.__file__).read_text(encoding="utf-8")
    )
    roots = {
        node.module.split(".")[0] if isinstance(node, ast.ImportFrom)
        else alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert roots <= {
        "__future__", "json", "dataclasses", "datetime", "enum", "typing"
    }


def test_model_serializer_uses_v2_json_mode_and_exact_v1_json_fallback():
    class V2:
        def __init__(self):
            self.calls = []

        def model_dump(self, **kwargs):
            self.calls.append(kwargs)
            return {"path": "v2"}

        def json(self):
            raise AssertionError("v1 fallback must not run")

    class V1:
        def __init__(self):
            self.calls = 0

        def json(self):
            self.calls += 1
            return '{"path":"v1","items":[1]}'

    v2 = V2()
    v1 = V1()
    assert serialization_stage._model_to_dict(v2) == {"path": "v2"}
    assert v2.calls == [{"mode": "json"}]
    assert serialization_stage._model_to_dict(v1) == {
        "path": "v1", "items": [1]
    }
    assert v1.calls == 1


def test_nested_dataclass_enum_datetime_and_container_conversion():
    class Status(Enum):
        READY = "ready"

    @dataclass
    class Record:
        status: Status
        observed_at: datetime
        values: tuple[int, ...]

    source = {7: [Record(Status.READY, datetime(2026, 9, 13, tzinfo=timezone.utc), (1, 2))]}
    assert serialization_stage._evidence_pipeline_to_dict(source) == {
        "7": [{
            "status": "ready",
            "observed_at": "2026-09-13T00:00:00+00:00",
            "values": [1, 2],
        }]
    }


def test_sets_and_frozensets_sort_composite_json_values_deterministically():
    source = {
        "sets": {("beta", 2), ("alpha", 1)},
        "frozen": frozenset({("z", 0), ("a", 9)}),
    }
    first = serialization_stage._evidence_pipeline_to_dict(source)
    second = serialization_stage._evidence_pipeline_to_dict(source)
    assert first == second == {
        "sets": [["alpha", 1], ["beta", 2]],
        "frozen": [["a", 9], ["z", 0]],
    }
    assert json.loads(json.dumps(first)) == first


def test_primitives_unknowns_detachment_and_no_source_mutation():
    unsupported = object()
    source = {
        "values": [None, "text", 4, 2.5, True, unsupported],
        "nested": {"items": [1, 2]},
    }
    before = [*source["nested"]["items"]]
    result = serialization_stage._evidence_pipeline_to_dict(source)
    assert result["values"] == [None, "text", 4, 2.5, True, None]
    assert result is not source
    assert result["nested"] is not source["nested"]
    assert result["nested"]["items"] is not source["nested"]["items"]
    result["nested"]["items"].append(3)
    assert source["nested"]["items"] == before
    assert source["values"][-1] is unsupported
