from __future__ import annotations

import json
from typing import Any


TASK_RELEVANCE_PRESENTER_CONTRACT_VERSION = (
    "promati.orchestrator.task_relevance_presenter.cp11.v1"
)


def _value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _claim_text(claim: dict[str, Any]) -> str:
    raw = str(claim.get("text") or "").strip()
    if not raw:
        return ""
    label = ""
    payload_text = raw
    if ": " in raw:
        candidate_label, candidate_payload = raw.split(": ", 1)
        if candidate_payload.lstrip().startswith("{"):
            label = candidate_label.strip()
            payload_text = candidate_payload.strip()
    if not payload_text.startswith("{"):
        return raw
    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw
    if not isinstance(payload, dict):
        return raw
    body = _value(
        payload.get("summary")
        or payload.get("title")
        or payload.get("family_name")
        or payload.get("item_id")
        or payload.get("family_code")
    )
    rendered_label = label or _value(
        payload.get("item_id") or payload.get("family_code")
    )
    if not body:
        # Structured evidence without a human-readable summary is an internal
        # evidence contract, not suitable public answer text. Treat the task as
        # uncovered so the presenter fails closed to the legacy/golden answer.
        return ""
    return f"{rendered_label}: {body}" if rendered_label else body


def _title(domain: str) -> str:
    return {
        "product": "Productinformatie",
        "technical": "Technische informatie",
        "inspection": "Inspectie-informatie",
        "org": "Organisatie-informatie",
        "rfq": "RFQ-informatie",
        "diagnostics": "Diagnostische informatie",
    }.get(domain, domain.capitalize() or "Aanvullende informatie")


def present_relevant_task_answer(
    plan: Any,
    legacy_answer: str | None,
    task_coverage_gate_cp10: dict[str, Any] | None,
    task_synthesis_coverage: dict[str, Any] | None,
    composition_authority: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any]]:
    """Render only covered, requested task units after CP10 grants authority."""
    gate = task_coverage_gate_cp10 or {}
    coverage = task_synthesis_coverage or {}
    authority = dict(composition_authority or {})
    excluded_domains = {
        _value(domain)
        for domain in (getattr(plan, "excluded_domains", None) or [])
        if _value(domain)
    }
    status: dict[str, Any] = {
        "contract_version": TASK_RELEVANCE_PRESENTER_CONTRACT_VERSION,
        "evaluated": True,
        "authoritative": False,
        "public_answer_replaced": False,
        "included_task_ids": [],
        "excluded_task_ids": [],
        "included_evidence_ids": [],
        "excluded_evidence_ids": [],
        "excluded_domains": sorted(excluded_domains),
        "task_decisions": [],
        "reason": None,
        "missing_required_tasks": [],
    }

    if gate.get("blocked") is True or gate.get("authoritative") is not True:
        gate_reason = _value(gate.get("reason")) or "coverage_blocked"
        missing_required_tasks = [
            _value(task_id)
            for task_id in list(gate.get("missing_required_tasks") or [])
            if _value(task_id)
        ]
        status["reason"] = gate_reason
        status["missing_required_tasks"] = missing_required_tasks
        for task in list(getattr(plan, "intent_tasks", None) or []):
            task_id = _value(getattr(task, "task_id", None))
            domain = _value(getattr(task, "domain", None))
            polarity = _value(getattr(task, "polarity", "requested")) or "requested"
            reason = (
                "excluded_domain"
                if domain in excluded_domains or polarity == "excluded"
                else gate_reason
            )
            status["excluded_task_ids"].append(task_id)
            status["task_decisions"].append({
                "task_id": task_id,
                "domain": domain,
                "included": False,
                "reason": reason,
            })
        authority.update({
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": gate_reason,
            "missing_required_tasks": missing_required_tasks,
            "task_presenter_cp11": status,
        })
        return legacy_answer, status, authority

    units_by_task: dict[str, list[dict[str, Any]]] = {}
    all_evidence_ids: set[str] = set()
    for unit in list(coverage.get("units") or []):
        if not isinstance(unit, dict):
            continue
        task_id = _value(unit.get("task_id"))
        if task_id:
            units_by_task.setdefault(task_id, []).append(unit)
        all_evidence_ids.update(
            _value(item) for item in list(unit.get("evidence_ids_used") or [])
            if _value(item)
        )

    sections: list[str] = []
    included_evidence: set[str] = set()
    for task in list(getattr(plan, "intent_tasks", None) or []):
        task_id = _value(getattr(task, "task_id", None))
        domain = _value(getattr(task, "domain", None))
        polarity = _value(getattr(task, "polarity", "requested")) or "requested"
        required = bool(getattr(task, "required", True))
        reason = None
        if domain in excluded_domains or polarity == "excluded":
            reason = "excluded_domain"
        elif polarity != "requested" or not required:
            reason = "not_requested"

        task_units = units_by_task.get(task_id, [])
        claims: list[str] = []
        task_evidence: set[str] = set()
        if reason is None:
            for unit in task_units:
                if unit.get("status") != "grounded" or _value(unit.get("domain")) != domain:
                    continue
                unit_claims = [
                    _claim_text(claim)
                    for claim in list(unit.get("claims") or [])
                    if isinstance(claim, dict)
                ]
                claims.extend(text for text in unit_claims if text)
                task_evidence.update(
                    _value(item)
                    for item in list(unit.get("evidence_ids_used") or [])
                    if _value(item)
                )
            if not claims:
                reason = "not_covered"

        if reason is not None:
            status["excluded_task_ids"].append(task_id)
            status["task_decisions"].append({
                "task_id": task_id, "domain": domain, "included": False,
                "reason": reason,
            })
            continue

        status["included_task_ids"].append(task_id)
        status["task_decisions"].append({
            "task_id": task_id, "domain": domain, "included": True,
            "reason": "covered_and_relevant",
        })
        included_evidence.update(task_evidence)
        lines = [f"{_title(domain)}:"]
        lines.extend(f"- {claim}" for claim in claims)
        sections.append("\n".join(lines))

    requested_not_covered = [
        row["task_id"] for row in status["task_decisions"]
        if row["reason"] == "not_covered"
    ]
    if requested_not_covered or not sections:
        status["reason"] = "not_covered" if requested_not_covered else "no_relevant_tasks"
        authority.update({
            "authoritative": False,
            "public_answer_authority": False,
            "public_answer_replaced": False,
            "blocked": True,
            "reason": status["reason"],
            "task_presenter_cp11": status,
        })
        return legacy_answer, status, authority

    status["included_evidence_ids"] = sorted(included_evidence)
    status["excluded_evidence_ids"] = sorted(all_evidence_ids - included_evidence)
    status.update({
        "authoritative": True,
        "public_answer_replaced": True,
        "reason": "presented_covered_relevant_tasks",
    })
    authority.update({
        "authoritative": True,
        "public_answer_authority": True,
        "public_answer_replaced": True,
        "blocked": False,
        "reason": "presented_covered_relevant_tasks",
        "task_presenter_cp11": status,
    })
    return "\n\n".join(sections), status, authority


__all__ = [
    "TASK_RELEVANCE_PRESENTER_CONTRACT_VERSION",
    "present_relevant_task_answer",
]
