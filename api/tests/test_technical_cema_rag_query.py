import unittest
from unittest.mock import patch

from app.routers import hybrid_api


def sql_context():
    return {
        "status": "ok",
        "count": 1,
        "results": [
            {
                "item_type": "section",
                "source_code": "CEMA_BELT_CONVEYORS_7",
                "title": "CEMA source result",
            }
        ],
    }


def rag_result():
    return {
        "vraag": "test",
        "antwoord": "test",
        "context_hits": [],
        "used_context": [],
    }


class TechnicalCemaRagQueryTests(unittest.TestCase):

    def test_definition_helper_returns_compact_grounded_query(self):
        original = (
            "Waar staat CEMA voor en wat betekent "
            "CEMA voor transportbanden?"
        )

        result = hybrid_api._technical_rag_query(
            original,
            "CEMA_BELT_CONVEYORS_7",
        )

        self.assertEqual(
            result,
            (
                "Conveyor Equipment Manufacturers Association "
                "CEMA betekenis acronym definition"
            ),
        )


    def test_normal_cema_helper_keeps_original_query(self):
        original = (
            "Welke CEMA-tabel geeft standaard "
            "skirtboard widths?"
        )

        result = hybrid_api._technical_rag_query(
            original,
            "CEMA_BELT_CONVEYORS_7",
        )

        self.assertEqual(
            result,
            original,
        )


    def test_non_cema_source_keeps_original_query(self):
        original = "Waar staat CEMA voor?"

        result = hybrid_api._technical_rag_query(
            original,
            "DUNLOP_DESIGN",
        )

        self.assertEqual(
            result,
            original,
        )


    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_definition_question_uses_compact_query_in_rag_call(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = sql_context()
        mock_post.return_value = rag_result()

        payload = hybrid_api.TechnicalAskRequest(
            vraag=(
                "Waar staat CEMA voor en wat betekent "
                "CEMA voor transportbanden?"
            ),
            source_code="CEMA_BELT_CONVEYORS_7",
            use_rag=True,
            limit=8,
        )

        hybrid_api.technical_assistant_ask(
            payload
        )

        mock_post.assert_called_once()

        args, kwargs = mock_post.call_args

        self.assertEqual(
            args[0],
            "/rag/query",
        )

        body = kwargs["json_body"]

        self.assertEqual(
            body["vraag"],
            (
                "Conveyor Equipment Manufacturers Association "
                "CEMA betekenis acronym definition"
            ),
        )

        self.assertEqual(
            body["doc_ids"],
            [
                "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
            ],
        )


if __name__ == "__main__":
    unittest.main()
