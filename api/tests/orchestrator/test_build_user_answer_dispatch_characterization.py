"""Characterize the service-owned ``_build_user_answer`` dispatch boundary."""
from __future__ import annotations

import ast
import copy
import inspect

import pytest

from app.orchestrator import service


class Fatal(BaseException):
    """A non-Exception sentinel used to characterize propagation."""


def _result(action: str, **payload):
    return {"action": action, "result": payload}


def _assert_unchanged(before, after):
    assert after == before


def test_ast_records_top_level_dispatch_shape_and_order_without_line_numbers():
    tree = ast.parse(inspect.getsource(service._build_user_answer))
    function = tree.body[0]

    top_level_types = [type(node) for node in function.body]
    assert top_level_types == [
        ast.Expr,
        ast.Assign,
        ast.Assign,
        ast.Assign,
        ast.For,
        ast.If,
        ast.For,
        ast.Return,
    ]
    assert ast.unparse(function.body[5].test) == "asset_result is not None"

    non_asset_loop = function.body[6]
    dispatch_conditions = [
        ast.unparse(node.test)
        for node in non_asset_loop.body
        if isinstance(node, ast.If)
    ]
    assert dispatch_conditions == [
        "not isinstance(specialist_result, dict)",
        "action == 'diagnostics_assistant'",
        "context_type == 'analysis_scope'",
        "action == 'product_assistant' or context_type == 'product_assistant'",
        "action == 'org_assistant' or context_type == 'org_assistant'",
        "action == 'technical_assistant' or context_type == 'technical_assistant'",
    ]
    assert isinstance(function.body[-1], ast.Return)
    assert isinstance(function.body[-1].value, ast.Constant)
    assert function.body[-1].value.value is None


@pytest.mark.parametrize("results", [[], [{"result": None}], [{"result": "text"}]])
def test_empty_and_non_mapping_results_fall_through_without_mutation(results):
    before = copy.deepcopy(results)

    assert service._build_user_answer(results) is None

    _assert_unchanged(before, results)


def test_asset_resolution_has_absolute_priority_and_preserves_inputs(monkeypatch):
    calls = []

    def display(name, code):
        calls.append((name, code))
        return f"display:{name}:{code}"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("later product dispatch must not run")

    monkeypatch.setattr(service, "_display_name_code", display)
    monkeypatch.setattr(service, "_build_multi_product_user_answer", forbidden)
    results = [
        _result("diagnostics_assistant", status="later"),
        _result(
            "asset_assistant",
            asset_resolution={},
            asset_context={
                "customer_code": "C-SYNTH",
                "site_code": "S-SYNTH",
                "area_name": "Area",
                "area_code": "A1",
                "installation_name": "Line",
                "installation_code": "L1",
            },
            entities={"band_code": "B-SYNTH"},
            message="primary message",
            kort_resultaat="compatibility message",
        ),
        _result("product_assistant", context_type="product_assistant"),
    ]
    before = copy.deepcopy(results)

    answer = service._build_user_answer(results, [" PRICE "])

    assert calls == [("Area", "A1"), ("Line", "L1")]
    assert answer == (
        "Klant: C-SYNTH\nPlaats: S-SYNTH\nGebied: display:Area:A1\n"
        "Installatie: display:Line:L1\nBandnummer: B-SYNTH\n\nprimary message"
    )
    _assert_unchanged(before, results)


def test_asset_compatibility_aliases_and_default_fallback_are_exact():
    results = [
        _result(
            "asset_assistant",
            asset_resolution={},
            asset_context="invalid legacy context",
            entities={"band_code": "B-ALIAS"},
            kort_resultaat="legacy short result",
        )
    ]

    answer = service._build_user_answer(results)

    assert answer == (
        "Klant: onbekend\nPlaats: onbekend\nGebied: onbekend\n"
        "Installatie: onbekend\nBandnummer: B-ALIAS\n\nlegacy short result"
    )


def test_latest_inspection_preserves_internal_mojibake_until_outer_stage_repairs_it():
    results = [
        _result(
            "analysis_assistant",
            asset_resolution={},
            asset_context={},
            intent="inspection_summary",
            resultaat=[
                {
                    "document_date": "2099-01-02",
                    "inspection_key": "I-SYNTH",
                    "scraper_type_raw": "Primair",
                    "locatie_raw": "Links",
                    "meshoogte_mm": 7,
                    "mes_vervangen": False,
                }
            ],
        )
    ]
    before = copy.deepcopy(results)

    answer = service._build_user_answer(results)

    assert "- Primair â€” Links: 7 mm" in answer
    assert "Geen mesvervanging geregistreerd" in answer
    _assert_unchanged(before, results)


@pytest.mark.parametrize(
    ("first", "expected_prefix"),
    [
        (_result("diagnostics_assistant", status="ok"), "Diagnose (diagnostics / overview): ok"),
        (_result("anything", context_type="analysis_scope", kort_resultaat="scope wins"), "scope wins"),
    ],
)
def test_non_asset_result_order_and_earlier_branch_priority(first, expected_prefix, monkeypatch):
    monkeypatch.setattr(
        service,
        "_build_multi_product_user_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("product branch must remain unreachable")
        ),
    )
    results = [first, _result("product_assistant", context_type="product_assistant")]

    assert service._build_user_answer(results).startswith(expected_prefix)


def test_multi_product_candidate_boundary_passes_identity_normalized_set_and_return(monkeypatch):
    results = [
        _result("ignored", context_type="unknown"),
        _result("ignored", context_type="product_assistant"),
    ]
    requested_information = [" Price ", "PRICE", " Inventory ", "", "  "]
    before_results = copy.deepcopy(results)
    before_requested = copy.deepcopy(requested_information)
    sentinel = object()
    calls = []

    def build(received_results, received_requested):
        calls.append((received_results, received_requested))
        return sentinel

    monkeypatch.setattr(service, "_build_multi_product_user_answer", build)

    answer = service._build_user_answer(results, requested_information)

    assert answer is sentinel
    assert len(calls) == 1
    assert calls[0][0] is results
    assert calls[0][1] == {"price", "inventory"}
    _assert_unchanged(before_results, results)
    _assert_unchanged(before_requested, requested_information)


@pytest.mark.parametrize("error", [RuntimeError("exception"), Fatal("base-exception")])
def test_multi_product_candidate_boundary_does_not_catch_any_throwable(monkeypatch, error):
    def raising(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "_build_multi_product_user_answer", raising)

    with pytest.raises(type(error), match=str(error)):
        service._build_user_answer([_result("product_assistant")])


def test_product_fallback_calls_helpers_once_in_order_with_exact_arguments(monkeypatch):
    calls = []
    results = [
        _result(
            "product_assistant",
            family_context={
                "results": [
                    {
                        "family_code": "F-SYNTH",
                        "strengths": "Sterk",
                        "limitations": "Beperkt",
                        "selection_advice": "Kies bewust",
                    }
                ]
            },
        )
    ]
    specialist_result = results[0]["result"]

    def multi(received_results, requested):
        calls.append(("multi", received_results, requested))
        return None

    def articles(received_result, *, include_inventory, include_price):
        calls.append(("articles", received_result, include_inventory, include_price))
        return ["Artikelregel"]

    monkeypatch.setattr(service, "_build_multi_product_user_answer", multi)
    monkeypatch.setattr(service, "_build_product_article_lines", articles)

    answer = service._build_user_answer(results, ["INVENTORY", " price "])

    assert calls == [
        ("multi", results, {"inventory", "price"}),
        ("articles", specialist_result, True, True),
    ]
    assert answer == (
        "F-SYNTH\n\nSterktes: Sterk\n\nBeperkingen: Beperkt\n\n"
        "Selectieadvies: Kies bewust\n\nArtikelregel"
    )


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_org_alias_dispatch_and_not_found_message_are_exact(selector):
    payload = {
        "result": {"status": "NOT_FOUND", "message": "synthetic not found"}
    }
    action = "org_assistant" if selector == "action" else "ignored"
    if selector == "context_type":
        payload["context_type"] = "org_assistant"

    assert service._build_user_answer([_result(action, **payload)]) == "synthetic not found"


@pytest.mark.parametrize("selector", ["action", "context_type"])
def test_technical_alias_dispatch_has_grounded_and_ungrounded_fallbacks(selector):
    payload = {
        "source_code": "CEMA_BELT_CONVEYORS_7",
        "technical_context": {"results": [{"source_title": "Synthetic source"}]},
    }
    action = "technical_assistant" if selector == "action" else "ignored"
    if selector == "context_type":
        payload["context_type"] = "technical_assistant"

    ungrounded = service._build_user_answer([_result(action, **payload)])
    payload["rag_context"] = {
        "used_context": [
            {"text": "Conveyor Equipment Manufacturers Association is stated here."}
        ]
    }
    grounded = service._build_user_answer([_result(action, **payload)])

    assert ungrounded == (
        "CEMA-referentiegegevens zijn beschikbaar uit Synthetic source. "
        "In dit specialistresultaat is geen definitierecord van CEMA aanwezig."
    )
    assert grounded == (
        "CEMA staat voor Conveyor Equipment Manufacturers Association. "
        "Bron: Synthetic source."
    )


def test_unhandled_mapping_and_exhausted_recognized_branches_return_none():
    results = [
        _result("unknown", context_type="unknown", message="must not leak"),
        _result("org_assistant", result="not structured"),
        _result("technical_assistant", source_code="OTHER"),
    ]
    before = copy.deepcopy(results)

    assert service._build_user_answer(results) is None

    _assert_unchanged(before, results)
