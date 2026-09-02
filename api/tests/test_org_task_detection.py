import unittest
from unittest.mock import patch

from app.routers import org_context


class OrgTaskDetectionTests(unittest.TestCase):

    @patch("app.routers.org_context.fetch_all")
    def test_it_category_does_not_match_inside_word_auditen(
        self,
        fetch_all_mock,
    ):
        fetch_all_mock.return_value = [
            {
                "taak_code": "PRINTER_SUPPORT",
                "taak_naam": "Printerproblemen",
                "categorie": "IT",
                "zoekwoorden": "printer, print, afdruk",
            }
        ]

        result = org_context.detect_taak_code(
            "Kun je de org-module technisch auditen?"
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
