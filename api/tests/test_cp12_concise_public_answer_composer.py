from app.orchestrator.response_shaping import compact_orchestrator_response
from app.orchestrator.task_concise_composer import (
    MAX_PUBLIC_ANSWER_BYTES,
    compose_concise_public_answer,
)


def _allowed():
    return (
        {"blocked": False, "authoritative": True},
        {"authoritative": True, "public_answer_replaced": True},
    )


def test_cp12_raw_machine_marker_is_never_published():
    gate, presenter = _allowed()
    answer, status = compose_concise_public_answer(
        'latest_position_measurement: {"value": 3.0}',
        "Veilige bestaande samenvatting.",
        task_coverage_gate_cp10=gate,
        task_presenter_cp11=presenter,
    )

    assert answer == "Veilige bestaande samenvatting."
    assert "latest_position_measurement:" not in answer
    assert status["reason"] == "unsafe_or_oversized_answer_fell_back"
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False


def test_cp12_long_bullet_answer_falls_back_to_safe_answer():
    gate, presenter = _allowed()
    answer, status = compose_concise_public_answer(
        "Techniek:\n" + "\n".join(f"- punt {index} " + "x" * 250 for index in range(20)),
        "Beknopte veilige uitleg.",
        task_coverage_gate_cp10=gate,
        task_presenter_cp11=presenter,
    )

    assert answer == "Beknopte veilige uitleg."
    assert status["output_bytes"] < MAX_PUBLIC_ANSWER_BYTES


def _oversized_mv1_inspection_source():
    return (
        'MV1 / Mengveld 1 Inspection: latest_blade_height: {'
        '"document_date":"2026-05-27","measurement_count":4,'
        '"min_meshoogte_mm":3.0,"max_meshoogte_mm":6.0,'
        '"position_measurements":[{'
        '"locatie_raw":"PRIMAIR","mes_vervangen":null,'
        '"meshoogte_mm":3.0,"scraper_type_raw":"H 1200-1000 SP/M3"}]}'
        + (" raw inspection evidence" * 400)
    )


def test_cp12_mv1_inspection_repair_precedes_wrong_safe_fallback():
    gate, presenter = _allowed()
    answer, status = compose_concise_public_answer(
        _oversized_mv1_inspection_source(),
        "Mengveld 1: 16 onderhoudsregels in de scope-ranglijst gevonden.",
        task_coverage_gate_cp10=gate,
        task_presenter_cp11=presenter,
    )

    for fragment in ("2026-05-27", "4 posities", "3.0 mm", "6.0 mm", "direct"):
        assert fragment in answer
    assert "16 onderhoudsregels" not in answer
    assert "latest_blade_height:" not in answer
    assert len(answer.encode("utf-8")) < 2_000
    assert status["reason"] == "mv1_inspection_answer_repaired"
    assert status["authoritative"] is True


def test_cp12_mv1_repair_cannot_override_blocked_authority():
    answer, status = compose_concise_public_answer(
        _oversized_mv1_inspection_source(),
        "Veilige fail-closed fallback.",
        task_coverage_gate_cp10={
            "blocked": True,
            "authoritative": False,
            "reason": "missing_required_tasks",
        },
        task_presenter_cp11={
            "authoritative": False,
            "public_answer_replaced": False,
        },
    )

    assert answer == "Veilige fail-closed fallback."
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False


def test_cp12_blocked_cp10_cp11_stays_non_authoritative():
    answer, status = compose_concise_public_answer(
        "Veilige legacytekst.",
        "Veilige legacytekst.",
        response_profile="debug",
        task_coverage_gate_cp10={
            "blocked": True,
            "authoritative": False,
            "reason": "missing_required_tasks",
        },
        task_presenter_cp11={
            "authoritative": False,
            "public_answer_replaced": False,
        },
    )

    assert answer == "Veilige legacytekst."
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False
    assert status["reason"] == "missing_required_tasks"


def test_cp12_compact_schema_has_no_new_debug_fields():
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": "Kort antwoord.",
        "query_plan": {"domains": ["technical"], "intent_tasks": []},
        "results": [],
        "evidence_pipeline": {
            "task_concise_composer_cp12": {"input_bytes": 99_999},
        },
    })

    assert set(compact) == {
        "status", "answer", "response_profile", "domains", "tasks", "coverage"
    }


def test_cp12_mv1_golden_fallback_remains_compact_and_clean():
    golden = (
        "MV1 / Mengveld 1 - directe aandacht nodig.\n"
        "Laatste inspectie: 2026-05-27.\n"
        "Meetbeeld: 4 posities, minimum meshhoogte 3.0 mm, maximum 6.0 mm.\n"
        "Onderhoudsprioriteit: direct actie nemen."
    )
    compact = compact_orchestrator_response({
        "status": "ok",
        "answer": golden,
        "query_plan": {"domains": ["inspection"], "intent_tasks": []},
        "results": [],
    })

    assert compact["answer"] == golden
    assert len(compact["answer"].encode("utf-8")) < 2_000
    for fragment in ("2026-05-27", "4 posities", "3.0 mm", "6.0 mm", "direct"):
        assert fragment in compact["answer"]
    assert "latest_position_measurement:" not in compact["answer"]
    assert "latest_blade_height:" not in compact["answer"]


def test_cp12_s6_missing_required_task_status_survives_in_debug_contract():
    gate = {
        "blocked": True,
        "authoritative": False,
        "reason": "missing_required_tasks",
        "missing_required_tasks": ["task_2_org"],
    }
    presenter = {
        "authoritative": False,
        "public_answer_replaced": False,
        "reason": "missing_required_tasks",
        "missing_required_tasks": ["task_2_org"],
    }
    _answer, status = compose_concise_public_answer(
        "Legacy diagnostics.", "Legacy diagnostics.", response_profile="debug",
        task_coverage_gate_cp10=gate, task_presenter_cp11=presenter,
    )

    assert gate["missing_required_tasks"] == ["task_2_org"]
    assert presenter["missing_required_tasks"] == ["task_2_org"]
    assert status["authoritative"] is False
    assert status["public_answer_replaced"] is False


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_cp12_") and callable(value):
            value()
    print("CP12 direct tests passed")
