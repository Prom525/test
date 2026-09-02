from app.orchestrator.service import (
    _build_user_answer,
)


def test_org_function_info_builds_user_answer():
    results = [
        {
            "action": "org_assistant",
            "result": {
                "status": "ok",
                "context_type": "org_assistant",
                "mode": "function_info",
                "result": {
                    "status": "ok",
                    "results": [
                        {
                            "person_id": 11,
                            "weergavenaam": "Aaron Thys",
                            "officiele_functienaam": (
                                "Operations Manager"
                            ),
                            "functie_naam": (
                                "Operations Manager / "
                                "MT-lid Operations & Organisatie"
                            ),
                            "afdeling": "Operations",
                            "kerntaken": (
                                "Operationele processen verbeteren."
                            ),
                        }
                    ],
                },
            },
        }
    ]

    answer = _build_user_answer(results)

    assert answer is not None
    assert "Aaron Thys" in answer
    assert "Operations Manager" in answer
    assert "Afdeling: Operations." in answer
    assert "Kerntaken:" in answer


def test_org_function_info_without_rows_returns_none():
    results = [
        {
            "action": "org_assistant",
            "result": {
                "status": "ok",
                "context_type": "org_assistant",
                "mode": "function_info",
                "result": {
                    "status": "ok",
                    "results": [],
                },
            },
        }
    ]

    answer = _build_user_answer(results)

    assert answer is None