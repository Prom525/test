from app.orchestrator.understanding import detect_band_code, understand_query


def _entity_value(plan, name):
    return getattr(plan.entities.get(name), "value", None)


def test_m3_dimension_is_not_a_band_code():
    question = (
        "Welke Belle Banne U-configuratie past op een transportband van 1200 mm, "
        "en wat zijn de technische limieten volgens CEMA? Geen inspectie of ORG."
    )

    plan = understand_query(question)

    assert _entity_value(plan, "band_code") is None
    assert _entity_value(plan, "belt_width_mm") == 1200


def test_dimension_phrases_are_not_band_codes():
    questions = (
        "transportband van 1000 mm",
        "band van 1200 mm",
        "breedte van 1400 mm",
        "1200 mm breed",
        # Reproduceert het vroege explicit-band pad dat VAN120 maakte.
        "band van 120 mm",
    )

    for question in questions:
        assert detect_band_code(question) is None, question
        assert _entity_value(understand_query(question), "band_code") is None


def test_real_band_codes_remain_intact():
    questions = (
        "band A319",
        "voor band A319",
        "laatste inspectiestatus A319",
    )

    for question in questions:
        assert detect_band_code(question).value == "A319"
        assert _entity_value(understand_query(question), "band_code") == "A319"


def test_existing_compact_letter_digit_codes_remain_intact():
    for code in ("B12", "R5", "E950", "MV1"):
        assert detect_band_code(code).value == code
