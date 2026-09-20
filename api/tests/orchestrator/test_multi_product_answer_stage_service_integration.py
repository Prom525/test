"""Service integration tests for the multi-product answer leaf boundary."""

from __future__ import annotations

import ast
import inspect

from app.orchestrator import service


def _product_result(**payload):
    return {"action": "product_assistant", "result": payload}


def test_runtime_monkeypatch_is_passed_to_stage_and_non_none_is_direct(monkeypatch):
    sentinel = object()
    calls = []
    results = [_product_result()]

    def runtime_builder(received_results, received_requested):
        calls.append((received_results, received_requested))
        return sentinel

    monkeypatch.setattr(service, "_build_multi_product_user_answer", runtime_builder)

    answer = service._build_user_answer(results, [" Price ", "PRICE"])

    assert answer is sentinel
    assert len(calls) == 1
    assert calls[0][0] is results
    assert calls[0][1] == {"price"}


def test_exact_none_continues_through_existing_single_family_fallback(monkeypatch):
    calls = []
    results = [
        _product_result(
            family_context={
                "results": [
                    {
                        "family_code": "F-SYNTH",
                        "strengths": "Sterk",
                        "limitations": "Beperkt",
                        "selection_advice": "Kies bewust",
                    }
                ]
            }
        )
    ]

    def runtime_builder(received_results, received_requested):
        calls.append((received_results, received_requested))
        return None

    monkeypatch.setattr(service, "_build_multi_product_user_answer", runtime_builder)

    answer = service._build_user_answer(results)

    assert len(calls) == 1
    assert calls[0][0] is results
    assert calls[0][1] == set()
    assert answer == (
        "F-SYNTH\n\nSterktes: Sterk\n\nBeperkingen: Beperkt\n\n"
        "Selectieadvies: Kies bewust"
    )


def test_service_has_one_stage_call_with_runtime_dependency_and_direct_return():
    tree = ast.parse(inspect.getsource(service._build_user_answer))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_multi_product_answer_stage"
    ]

    assert len(calls) == 1
    assert [ast.unparse(argument) for argument in calls[0].args] == [
        "results",
        "requested",
        "_build_multi_product_user_answer",
    ]
    returns = [
        ast.unparse(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert "multi_product_answer_stage_result.delegated_answer" in returns
