"""Dependency-free diagnostics answer presentation."""


def run_diagnostics_answer_stage(specialist_result: dict) -> str:
    status = str(specialist_result.get("status") or "unknown")
    mode = str(specialist_result.get("mode") or "overview")
    domain = str(specialist_result.get("domain") or "diagnostics")

    summary = specialist_result.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    findings = specialist_result.get("findings")
    if not isinstance(findings, list):
        findings = []

    recommended_actions = specialist_result.get("recommended_actions")
    if not isinstance(recommended_actions, list):
        recommended_actions = []

    answer_lines = [f"Diagnose ({domain} / {mode}): {status}"]

    gpt_diagnosis = summary.get("gpt_diagnosis")
    if isinstance(gpt_diagnosis, dict):
        headline = gpt_diagnosis.get("headline")
        if headline:
            answer_lines.extend(["", str(headline)])

        interpretation = gpt_diagnosis.get("interpretation")
        if isinstance(interpretation, list):
            for line in interpretation[:8]:
                if line:
                    answer_lines.append(f"- {line}")
    elif summary.get("message"):
        answer_lines.extend(["", str(summary.get("message"))])
    else:
        compact_fields = (
            ("view_name", "View"),
            ("object_name", "Object"),
            ("row_count", "Rijen"),
            ("dependencies_found", "Dependencies"),
            ("objects_checked", "Objecten gecontroleerd"),
            ("comparisons_made", "Vergelijkingen"),
        )
        compact_values = []
        for key, label in compact_fields:
            value = summary.get(key)
            if value is not None:
                compact_values.append(f"{label}: {value}")
        if compact_values:
            answer_lines.extend(["", "; ".join(compact_values)])

    if findings:
        answer_lines.extend(["", "Bevindingen:"])
        for finding in findings[:8]:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity") or "info").upper()
            issue = finding.get("issue") or finding.get("message")
            if issue:
                answer_lines.append(f"- [{severity}] {issue}")

    if recommended_actions:
        answer_lines.extend(["", "Aanbevolen vervolgstappen:"])
        for action_text in recommended_actions[:5]:
            if action_text:
                answer_lines.append(f"- {action_text}")

    return "\n".join(answer_lines)


__all__ = ["run_diagnostics_answer_stage"]
