from typing import Dict, List


def evaluate_engineering_rules(extracted_specs: Dict) -> Dict:
    classification = extracted_specs.get("classification") or {}

    function_type = classification.get("function_type")
    duty_class = classification.get("duty_class")
    lagging_class = classification.get("lagging_class")

    missing_fields: List[str] = []
    warnings: List[str] = []

    # -----------------------------------
    # DRIVE PULLEY RULES
    # -----------------------------------

    if function_type == "AANDRIJFTROMMEL":

        if not extracted_specs.get("balancering"):
            missing_fields.append("balancering")

        if not extracted_specs.get("tir_mm"):
            warnings.append(
                "Aandrijftrommel zonder TIR specificatie."
            )

    # -----------------------------------
    # HEAVY DUTY RULES
    # -----------------------------------

    if duty_class == "HEAVY_DUTY":

        if not extracted_specs.get("tir_mm"):
            missing_fields.append("tir_mm")

        if not extracted_specs.get("materiaal_as"):
            missing_fields.append("materiaal_as")

        if not extracted_specs.get("materiaal_mantel"):
            missing_fields.append("materiaal_mantel")

    # -----------------------------------
    # LAGGING RULES
    # -----------------------------------

    if lagging_class == "RUBBER_DIAMANT":

        if not extracted_specs.get("lagging_dikte_mm"):
            missing_fields.append("lagging_dikte_mm")

    # -----------------------------------
    # GENERAL WARNINGS
    # -----------------------------------

    if extracted_specs.get("shaft_diameter_mm") and extracted_specs.get("diameter_de_mm"):

        shaft = extracted_specs["shaft_diameter_mm"]
        pulley = extracted_specs["diameter_de_mm"]

        if shaft > pulley * 0.4:
            warnings.append(
                "Controleer verhouding asdiameter versus trommeldiameter."
            )

    return {
        "missing_fields": sorted(list(set(missing_fields))),
        "warnings": warnings,
    }