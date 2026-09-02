import unittest
from unittest.mock import patch

from app.routers import org_context


class OrgFunctionInfoGuardTests(unittest.TestCase):

    @patch("app.routers.org_context.fetch_all")
    @patch(
        "app.routers.org_context.detect_person_or_function_from_question"
    )
    def test_unknown_function_question_does_not_return_broad_people_list(
        self,
        detect_mock,
        fetch_all_mock,
    ):
        detect_mock.return_value = {
            "person_name": None,
            "functie_code": None,
        }

        # Sentinel: huidig fout gedrag zou deze brede rij teruggeven.
        fetch_all_mock.return_value = [
            {
                "sentinel": "BROAD_LIST_SHOULD_NOT_BE_RETURNED",
            }
        ]

        result = org_context.function_info(
            q="Kun je de org-module technisch auditen?"
        )

        self.assertEqual(
            result.get("status"),
            "not_found",
        )

        self.assertEqual(
            result.get("results", []),
            [],
        )

        fetch_all_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
