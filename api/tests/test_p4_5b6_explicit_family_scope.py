from __future__ import annotations

from app.routers.hybrid_api import _sanitize_product_family_context


TPH = {
    "family_code": "PROM-TPH-HD",
    "family_name": "Promati TPH HD",
    "product_type": "bandschraper",
    "short_description": "Heavy-duty primaire schraper",
}

BB_U = {
    "family_code": "BB-U",
    "family_name": "Belle Banne U",
    "product_type": "bandschraper",
    "short_description": "Secundaire schraper",
}


def context(*rows):
    return {
        "status": "ok",
        "context_type": "product_family_context",
        "results": list(rows),
        "count": len(rows),
        "selection_matrix_included": True,
        "selection_matrix": [{"family_code": "PROM-TPH-HD"}],
    }


def test_explicit_tph_survives_broad_question_with_non_scraper_families():
    result = _sanitize_product_family_context(
        context(TPH),
        vraag=(
            "Beoordeel dit concept met TPH HD, Belle Banne U, "
            "Proload en Impact Bars"
        ),
        family_code="PROM-TPH-HD",
    )
    assert result["results"] == [TPH]
    assert result["count"] == 1
    assert result["explicit_family_scope"] is True


def test_explicit_scope_rejects_cross_family_record():
    result = _sanitize_product_family_context(
        context(BB_U),
        vraag="Vergelijk TPH HD en Belle Banne U",
        family_code="PROM-TPH-HD",
    )
    assert result["results"] == []
    assert result["count"] == 0
    assert "expliciete family scope" in result["note"]


def test_explicit_scope_keeps_only_matching_identity():
    result = _sanitize_product_family_context(
        context(TPH, BB_U),
        vraag="Vergelijk TPH HD en Belle Banne U",
        family_code="BB-U",
    )
    assert result["results"] == [BB_U]


def test_selection_matrix_is_not_destroyed_by_family_scope():
    original = context(TPH)
    result = _sanitize_product_family_context(
        original,
        vraag="Vergelijk TPH HD met Proload",
        family_code="PROM-TPH-HD",
    )
    assert result["selection_matrix"] == original["selection_matrix"]


def test_without_explicit_family_legacy_sanitizer_still_blocks_scraper_fallback():
    result = _sanitize_product_family_context(
        context(TPH),
        vraag="Vertel over Proload",
    )
    assert result["results"] == []
    assert result["selection_matrix"] == []
