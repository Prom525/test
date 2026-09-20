"""Service integration tests for the single-family product answer stage."""

from __future__ import annotations

from app.orchestrator import service


def _product_result(action="product_assistant", *, context_type=None, family_name="Family"):
    result = {
        "family_context": {
            "results": [
                {
                    "family_name": family_name,
                    "strengths": None,
                    "limitations": None,
                    "selection_advice": None,
                }
            ]
        }
    }
    if context_type is not None:
        result["context_type"] = context_type
    return {"action": action, "result": result}


def test_action_alias_uses_runtime_monkeypatched_dependency_and_returns_answer(monkeypatch):
    calls = []
    results = [_product_result()]
    monkeypatch.setattr(service, "_build_multi_product_user_answer", lambda *_args: None)

    def articles(received, *, include_inventory, include_price):
        calls.append((received, include_inventory, include_price))
        return ["article"]

    monkeypatch.setattr(service, "_build_product_article_lines", articles)

    assert service._build_user_answer(results, [" Price "]) == "Family\n\narticle"
    assert calls == [(results[0]["result"], False, True)]


def test_context_type_alias_reaches_same_stage(monkeypatch):
    results = [_product_result("other", context_type="product_assistant")]
    monkeypatch.setattr(service, "_build_multi_product_user_answer", lambda *_args: None)

    assert service._build_user_answer(results) == "Family"


def test_exact_none_falls_through_to_next_result(monkeypatch):
    results = [
        {"action": "product_assistant", "result": {"family_context": {"results": []}}},
        _product_result(family_name="Second"),
    ]
    monkeypatch.setattr(service, "_build_multi_product_user_answer", lambda *_args: None)

    assert service._build_user_answer(results) == "Second"


def test_exact_none_for_all_results_reaches_general_none(monkeypatch):
    results = [
        {"action": "product_assistant", "result": {"family_context": {"results": []}}},
        {"action": "other", "result": {}},
    ]
    monkeypatch.setattr(service, "_build_multi_product_user_answer", lambda *_args: None)

    assert service._build_user_answer(results) is None
