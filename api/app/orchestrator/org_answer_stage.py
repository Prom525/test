"""Dependency-free ORG answer presentation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrgAnswerStageResult:
    answer: str | None


def run_org_answer_stage(
    specialist_result: dict,
) -> OrgAnswerStageResult:
    org_result = specialist_result.get("result")

    if not isinstance(org_result, dict):
        return OrgAnswerStageResult(answer=None)

    org_status = str(
        org_result.get("status") or specialist_result.get("status") or ""
    ).lower()
    message = org_result.get("message")

    if org_status == "not_found" and message:
        return OrgAnswerStageResult(answer=str(message))

    mode = str(specialist_result.get("mode") or "")

    if mode == "location_info":
        location_rows = org_result.get("results")

        if isinstance(location_rows, list):
            locations = []

            for location in location_rows:
                if not isinstance(location, dict):
                    continue

                address = location.get("adres")
                place = location.get("plaats")
                label = location.get("locatie") or place

                if address:
                    if label:
                        locations.append(f"- {label}: {address}")
                    else:
                        locations.append(f"- {address}")
                elif place:
                    land = location.get("land")
                    value = str(place)

                    if land:
                        value += f", {land}"

                    if label:
                        locations.append(f"- {label}: {value}")
                    else:
                        locations.append(f"- {value}")

            if locations:
                return OrgAnswerStageResult(
                    answer="\n".join(["Promati is gevestigd op:", *locations])
                )

    if mode == "function_info":
        function_rows = org_result.get("results")

        if not isinstance(function_rows, list):
            return OrgAnswerStageResult(answer=None)

        valid_rows = [row for row in function_rows if isinstance(row, dict)]

        if not valid_rows:
            return OrgAnswerStageResult(answer=None)

        row = valid_rows[0]
        display_name = row.get("weergavenaam") or "Onbekende persoon"
        function_name = row.get("officiele_functienaam") or row.get("functie_naam")
        department = row.get("afdeling")
        core_tasks = row.get("kerntaken")
        answer_lines = []

        if function_name:
            answer_lines.append(f"{display_name} is {function_name}.")
        else:
            answer_lines.append(f"Functiegegevens gevonden voor {display_name}.")

        if department:
            answer_lines.append(f"Afdeling: {department}.")

        if core_tasks:
            answer_lines.extend(["", "Kerntaken:", str(core_tasks)])

        return OrgAnswerStageResult(answer="\n".join(answer_lines))

    return OrgAnswerStageResult(answer=None)
