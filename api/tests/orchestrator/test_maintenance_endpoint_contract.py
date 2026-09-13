"""Networkless contract for the existing analysis maintenance function."""
from __future__ import annotations

from app.routers import analysis_api_v10


def _row():
    return {
        "lijn_code": "GSL", "band_norm": "A319", "position_hint": "WEST",
        "scraper_types": "RI 1400-1350", "cycle_start": "2025-05-01",
        "cycle_end": "2026-05-05", "meetpunten": 4,
        "avg_meshoogte_mm": 5.0, "start_meshoogte_mm": 10.0,
        "eind_meshoogte_mm": 3.0, "slijtage_mm_per_dag": 0.01,
        "geschatte_dagen_tot_3mm": 0,
        "geschatte_vervangdatum_bij_3mm": "2026-05-05",
        "status_3mm": "NU VERVANGEN", "prioriteit": 1,
        "first_sheet_analysis_key": "first", "last_sheet_analysis_key": "last",
        "first_sheet_instance_key": "first-i", "last_sheet_instance_key": "last-i",
        "first_canonical_inspection_key": "first-c",
        "last_canonical_inspection_key": "last-c", "source_file": "synthetic.xlsx",
        "sheet_raw": "synthetic",
    }


def test_maintenance_positions_passes_scope_and_limit_and_preserves_public_source_fields(monkeypatch):
    captured = {}
    def fake_fetch_all(sql, params):
        captured.update(sql=sql, params=params)
        return [_row()]
    monkeypatch.setattr(analysis_api_v10, "fetch_all", fake_fetch_all)
    result = analysis_api_v10.maintenance_positions("GSL", "A319", 20)
    assert captured["params"] == {"limit": 20, "lijn_code": "GSL", "band_code": "A319"}
    assert "lijn_code = :lijn_code" in captured["sql"]
    assert "band_norm = :band_code" in captured["sql"]
    assert result["intent"] == "maintenance_positions"
    assert isinstance(result["resultaat"], list)
    row = result["resultaat"][0]
    for key in ("lijn_code", "band_norm", "position_hint", "scraper_types",
                "cycle_end", "eind_meshoogte_mm", "status_3mm", "prioriteit"):
        assert key in row


def test_maintenance_positions_zero_rows_is_authoritative_not_transport_error(monkeypatch):
    monkeypatch.setattr(analysis_api_v10, "fetch_all", lambda sql, params: [])
    result = analysis_api_v10.maintenance_positions("GSL", None, 20)
    assert result == {
        "intent": "maintenance_positions",
        "kort_resultaat": "0 onderhoudsposities gevonden.",
        "trend_patronen": ["Prioriteit 1: 0", "Prioriteit 2: 0",
                           "Prestatiegrens 6 mm geraakt/nabij: 0", "Op of onder 6 mm: 0"],
        "resultaat": [],
    }

