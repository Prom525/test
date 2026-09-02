from __future__ import annotations

from typing import Any


STANDARD_REFERENCES = {
    "NF_H95_330": {
        "title": "Tambours, arbres, paliers — série lourde",
        "use_for": [
            "pulley_standard_dimensions",
            "shaft_class_suggestion",
            "bearing_position_context",
        ],
        "note": (
            "Interne PROMATI normreferentie. Gebruik voor voorstellen, "
            "niet voor automatische definitieve invulling."
        ),
    },
    "DIN_15207_1": {
        "title": "Idlers for belt conveyors handling loose bulk materials",
        "use_for": [
            "idler_dimensions",
            "roller_nominal_diameters",
            "spindle_end_context",
        ],
        "note": "Voor rollen/idlers, niet voor trommel-asdiameter.",
    },
    "AS_1403": {
        "title": "Design of rotating steel shafts",
        "use_for": [
            "shaft_design_warning",
            "calculation_required",
            "load_data_required",
        ],
        "note": (
            "Gebruik voor engineeringcontrole van roterende stalen assen. "
            "Definitieve berekening vereist belastinggegevens."
        ),
    },
    "EN_620": {
        "title": "Safety and EMC requirements for fixed belt conveyors for bulk materials",
        "use_for": [
            "conveyor_safety_context",
            "guarding_context",
            "nip_point_context",
        ],
        "note": "Voor safety/context, niet voor asdiameter.",
    },
}


# Eerste gecontroleerde seed uit NF H95-330.
# Bewust klein houden. Later uitbreiden met meer rijen.
# Let op: dit zijn normvoorstellen, geen definitieve engineeringberekening.
NF_H95330_SHAFT_CLASS_SEED = [
    # D = 400
    {
        "diameter_mm": 400,
        "belt_width_mm": 500,
        "shaft_classes_mm": [50, 65, 80],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 400,
        "belt_width_mm": 650,
        "shaft_classes_mm": [50, 65, 80],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 400,
        "belt_width_mm": 800,
        "shaft_classes_mm": [50, 65, 80],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 400,
        "belt_width_mm": 1000,
        "shaft_classes_mm": [65, 80, 100],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 400,
        "belt_width_mm": 1200,
        "shaft_classes_mm": [65, 80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 400,
        "belt_width_mm": 1400,
        "shaft_classes_mm": [65, 80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },

    # D = 500
    {
        "diameter_mm": 500,
        "belt_width_mm": 500,
        "shaft_classes_mm": [50, 65, 80],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 650,
        "shaft_classes_mm": [65, 80, 100],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 800,
        "shaft_classes_mm": [65, 80, 100],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 1000,
        "shaft_classes_mm": [80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 1200,
        "shaft_classes_mm": [80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 1400,
        "shaft_classes_mm": [80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 1600,
        "shaft_classes_mm": [100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 1800,
        "shaft_classes_mm": [100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 500,
        "belt_width_mm": 2000,
        "shaft_classes_mm": [100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },

    # D = 630
    {
        "diameter_mm": 630,
        "belt_width_mm": 800,
        "shaft_classes_mm": [80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 1000,
        "shaft_classes_mm": [80, 100, 125],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 1200,
        "shaft_classes_mm": [80, 100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 1400,
        "shaft_classes_mm": [100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 1600,
        "shaft_classes_mm": [100, 125, 160, 200],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 1800,
        "shaft_classes_mm": [100, 125, 160, 200],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 630,
        "belt_width_mm": 2000,
        "shaft_classes_mm": [100, 125, 160, 200],
        "source": "NF_H95_330",
        "confidence": "medium",
    },

    # D = 800
    {
        "diameter_mm": 800,
        "belt_width_mm": 1000,
        "shaft_classes_mm": [100, 125, 160],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 800,
        "belt_width_mm": 1200,
        "shaft_classes_mm": [100, 125, 160, 200],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 800,
        "belt_width_mm": 1400,
        "shaft_classes_mm": [125, 160, 200],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 800,
        "belt_width_mm": 1600,
        "shaft_classes_mm": [125, 160, 200, 240],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 800,
        "belt_width_mm": 1800,
        "shaft_classes_mm": [125, 160, 200, 240],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
    {
        "diameter_mm": 800,
        "belt_width_mm": 2000,
        "shaft_classes_mm": [160, 200, 240, 280],
        "source": "NF_H95_330",
        "confidence": "medium",
    },
]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace("Ø", "")
            .replace("ø", "")
            .replace("mm", "")
            .replace(",", ".")
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _pick_first_number(specs: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = _to_float(specs.get(key))
        if value is not None:
            return value
    return None


def _pick_first_value(specs: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = specs.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _unique(items: list[str]) -> list[str]:
    result = []
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _missing_set(missing_fields: list[str] | None) -> set[str]:
    return {
        str(field).strip().lower()
        for field in (missing_fields or [])
        if str(field).strip()
    }


def infer_belt_width_candidates(specs: dict[str, Any]) -> tuple[list[float], str]:
    """
    Geeft mogelijke bandbreedtes terug.

    Voorkeur:
    1. expliciete bandbreedte
    2. voorzichtige afleiding uit mantellengte/drum_width

    De afleiding is bewust low-confidence, want mantellengte L is niet hetzelfde
    als bandbreedte l. NF H95-330 gebruikt l als courroiebreedte.
    """

    explicit_belt_width = _pick_first_number(
        specs,
        [
            "belt_width_mm",
            "conveyor_belt_width_mm",
            "bandbreedte_mm",
            "belt_width",
        ],
    )

    if explicit_belt_width:
        return [explicit_belt_width], "explicit"

    drum_width = _pick_first_number(
        specs,
        [
            "drum_width_mm",
            "mantel_lengte_mm",
            "shell_length_mm",
            "L",
        ],
    )

    if not drum_width:
        return [], "unknown"

    candidates: list[float] = []

    # NF H95-330 figuur gebruikt L als trommellengte met opslag t.o.v. l.
    # Zonder exacte context geven we alleen kandidaten, geen harde waarde.
    if drum_width <= 750:
        candidates.append(drum_width - 100)
    elif drum_width <= 1200:
        candidates.append(drum_width - 150)
    else:
        candidates.append(drum_width - 200)
        candidates.append(drum_width - 150)

    candidates = [
        value
        for value in candidates
        if value and value > 0
    ]

    return candidates, "inferred_from_drum_width"


def find_nf_h95330_seed_entry(
    diameter_mm: float | None,
    belt_width_candidates: list[float],
) -> dict[str, Any] | None:
    if not diameter_mm or not belt_width_candidates:
        return None

    best_entry = None
    best_score = None
    best_match = None

    for entry in NF_H95330_SHAFT_CLASS_SEED:
        standard_diameter = float(entry["diameter_mm"])
        diameter_delta = abs(standard_diameter - diameter_mm)

        # Trommeldiameter moet redelijk dichtbij liggen.
        # Anders geen normvoorstel geven.
        if diameter_delta > 25:
            continue

        for belt_width in belt_width_candidates:
            standard_belt_width = float(entry["belt_width_mm"])
            width_delta = abs(standard_belt_width - belt_width)

            # Bandbreedte mag wat ruimer zijn, omdat we soms uit drum_width afleiden.
            if width_delta > 300:
                continue

            score = diameter_delta * 3 + width_delta

            if best_score is None or score < best_score:
                best_score = score
                best_entry = entry
                best_match = {
                    "input_diameter_mm": diameter_mm,
                    "matched_diameter_mm": standard_diameter,
                    "diameter_delta_mm": diameter_delta,
                    "input_belt_width_candidate_mm": belt_width,
                    "matched_belt_width_mm": standard_belt_width,
                    "belt_width_delta_mm": width_delta,
                    "match_score": score,
                }

    if not best_entry:
        return None

    result = dict(best_entry)
    result["match"] = best_match
    return result


def suggest_nf_h95330_shaft_classes(
    specs: dict[str, Any],
    missing_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Geeft mogelijke as-/lagerdiameterklassen uit NF H95-330 terug.

    Belangrijk:
    - vult niets definitief in
    - geeft PROPOSED_NOT_CONFIRMED terug
    - vereist engineering/leverancierbevestiging
    """

    missing = _missing_set(missing_fields)

    existing_shaft = _pick_first_number(
        specs,
        [
            "shaft_diameter_mm",
            "as_diameter_mm",
            "d1_mm",
            "D1",
        ],
    )

    if existing_shaft and "shaft_diameter_mm" not in missing:
        return []

    diameter_mm = _pick_first_number(
        specs,
        [
            "diameter_mm",
            "diameter_de_mm",
            "DE",
            "pulley_diameter_mm",
        ],
    )

    belt_width_candidates, belt_width_source = infer_belt_width_candidates(specs)
    entry = find_nf_h95330_seed_entry(diameter_mm, belt_width_candidates)

    if not entry:
        return []

    confidence = entry.get("confidence", "medium")
    match = entry.get("match") or {}

    if belt_width_source != "explicit":
        confidence = "low"

    if match.get("diameter_delta_mm", 0) > 0 or match.get("belt_width_delta_mm", 0) > 0:
        if confidence == "medium":
            confidence = "low"

    return [
        {
            "field": "shaft_diameter_mm",
            "label": "Asdiameter D1 / lagerdiameter d",
            "status": "PROPOSED_NOT_CONFIRMED",
            "proposed_values": entry["shaft_classes_mm"],
            "unit": "mm",
            "source": entry["source"],
            "confidence": confidence,
            "reason": (
                "NF H95-330 normvoorstel op basis van "
                f"trommeldiameter D={diameter_mm:g} mm. "
                f"Bandbreedtebron: {belt_width_source}. "
                f"Dichtstbijzijnde match: D={match.get('matched_diameter_mm')} mm, "
                f"bandbreedte={match.get('matched_belt_width_mm')} mm. "
                "Meerdere as-/lagerdiameterklassen zijn mogelijk; waarde niet automatisch invullen."
            ),
            "match": match,
            "engineering_note": (
                "Dit is een norm-/catalogusvoorstel. Definitieve D1 vereist controle "
                "op belasting, buiging, torsie, lagerafstand, passing, stress raisers "
                "en constructie-uitvoering."
            ),
            "supplier_question": (
                "Bevestig asdiameter D1, lagerdiameter d/D2, lagerhuis, lagerafstand A "
                "en de toegepaste berekeningsgrondslag."
            ),
            "may_auto_fill": False,
            "requires_confirmation": True,
        }
    ]


def build_pulley_standard_suggestions(
    specs: dict[str, Any],
    missing_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    product_type = str(
        specs.get("product_type")
        or specs.get("productgroep")
        or specs.get("product_group")
        or ""
    ).upper()

    # Als product_type ontbreekt, maar diameter/drum_width aanwezig zijn,
    # behandelen we dit voorlopig als mogelijke trommelcontext.
    has_pulley_dimensions = bool(
        _pick_first_number(specs, ["diameter_mm", "diameter_de_mm", "DE"])
        and _pick_first_number(specs, ["drum_width_mm", "mantel_lengte_mm", "L"])
    )

    if product_type and "TROMMEL" not in product_type and "PULLEY" not in product_type:
        return []

    if not product_type and not has_pulley_dimensions:
        return []

    suggestions: list[dict[str, Any]] = []
    suggestions.extend(
        suggest_nf_h95330_shaft_classes(
            specs=specs,
            missing_fields=missing_fields,
        )
    )

    return suggestions


def build_pulley_supplier_questions(
    specs: dict[str, Any],
    missing_fields: list[str] | None = None,
) -> list[str]:
    missing = _missing_set(missing_fields)
    questions: list[str] = []

    suggestions = build_pulley_standard_suggestions(
        specs=specs,
        missing_fields=missing_fields,
    )

    for suggestion in suggestions:
        question = suggestion.get("supplier_question")
        if question:
            questions.append(question)

    if "balancing_norm" in missing or not specs.get("balancing_norm"):
        questions.append(
            "Bevestig de vereiste balanceerklasse/norm voor deze trommel "
            "en lever indien van toepassing een balanceerrapport mee."
        )

    if "seal_type" in missing or not specs.get("seal_type"):
        bearing_context = (
            specs.get("bearing_housing")
            or specs.get("bearing_housing_type")
            or specs.get("bearing_type")
            or specs.get("bearing")
            or "het lagerhuis"
        )

        questions.append(
            f"Bevestig het seal type / afdichtingsconcept voor {bearing_context} "
            "en vermeld of dit geschikt is voor de bedrijfsomgeving."
        )

    if "tolerance_class" in missing or not specs.get("tolerance_class"):
        questions.append(
            "Bevestig de toegepaste tolerantienorm/klasse en de kritische "
            "toleranties voor as-, lager- en trommelmaten."
        )

    return _unique(questions)


def build_pulley_engineering_notes(
    specs: dict[str, Any],
    missing_fields: list[str] | None = None,
) -> list[str]:
    notes: list[str] = []

    suggestions = build_pulley_standard_suggestions(
        specs=specs,
        missing_fields=missing_fields,
    )

    for suggestion in suggestions:
        note = suggestion.get("engineering_note")
        if note:
            notes.append(note)

    if suggestions:
        notes.append(
            "AS 1403-context: definitieve asdimensionering vereist belastinggegevens "
            "zoals buigmoment, torsie, axiale belasting, materiaalgegevens, lagerafstand, "
            "passingen, keyways/splines en deflectiecontrole."
        )

    return _unique(notes)


def evaluate_pulley_knowledge(
    specs: dict[str, Any],
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    suggestions = build_pulley_standard_suggestions(
        specs=specs,
        missing_fields=missing_fields,
    )

    supplier_questions = build_pulley_supplier_questions(
        specs=specs,
        missing_fields=missing_fields,
    )

    engineering_notes = build_pulley_engineering_notes(
        specs=specs,
        missing_fields=missing_fields,
    )

    return {
        "product_type": "TROMMEL",
        "standard_references": STANDARD_REFERENCES,
        "standard_suggestions": suggestions,
        "supplier_questions": supplier_questions,
        "engineering_notes": engineering_notes,
        "requires_engineering": bool(suggestions),
    }