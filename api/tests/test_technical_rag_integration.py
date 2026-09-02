import unittest
from unittest.mock import patch

from app.routers import hybrid_api


def sql_context():
    return {
        "status": "ok",
        "count": 1,
        "results": [
            {
                "item_type": "table",
                "source_code": "CEMA_BELT_CONVEYORS_7",
                "title": "SQL primary result",
            }
        ],
    }


def rag_result():
    return {
        "status": "ok",
        "answer": "Aanvullende technische RAG-context.",
        "context_hits": [
            {
                "doc_id":
                    "cema_belt_conveyors_o_0000730_with_new_logo_ng_2",
                "text": "CEMA context",
            }
        ],
        "used_context": [
            "CEMA context",
        ],
    }


class TechnicalRagIntegrationTests(unittest.TestCase):

    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_use_rag_false_does_not_call_rag(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = sql_context()

        payload = hybrid_api.TechnicalAskRequest(
            vraag="standaard skirtboard widths",
            source_code="CEMA_BELT_CONVEYORS_7",
            use_rag=False,
            limit=5,
        )

        response = hybrid_api.technical_assistant_ask(
            payload
        )

        self.assertEqual(
            response["technical_context"],
            sql_context(),
        )

        self.assertNotIn(
            "rag_context",
            response,
        )

        mock_post.assert_not_called()


    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_use_rag_true_cema_is_exactly_scoped(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = sql_context()
        mock_post.return_value = rag_result()

        payload = hybrid_api.TechnicalAskRequest(
            vraag="standaard skirtboard widths",
            source_code="CEMA_BELT_CONVEYORS_7",
            use_rag=True,
            limit=5,
        )

        response = hybrid_api.technical_assistant_ask(
            payload
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

        # SQL blijft primair en intact.
        self.assertEqual(
            response["technical_context"],
            sql_context(),
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
            "standaard skirtboard widths",
        )

        self.assertEqual(
            body["doc_ids"],
            [
                "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
            ],
        )

        self.assertEqual(
            response["rag_source_route"],
            "/rag/query",
        )

        self.assertEqual(
            response["rag_context"]["status"],
            "ok",
        )

        self.assertEqual(
            response["rag_context"]["scope_doc_ids"],
            [
                "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
            ],
        )


    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_unknown_source_never_broadens_to_all_books(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = {
            "status": "ok",
            "count": 1,
            "results": [],
        }

        payload = hybrid_api.TechnicalAskRequest(
            vraag="technische informatie",
            source_code="DOES_NOT_EXIST",
            use_rag=True,
            limit=5,
        )

        response = hybrid_api.technical_assistant_ask(
            payload
        )

        mock_post.assert_not_called()

        self.assertNotIn(
            "rag_context",
            response,
        )


    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_rag_failure_does_not_break_sql_response(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = sql_context()

        mock_post.side_effect = RuntimeError(
            "simulated RAG failure"
        )

        payload = hybrid_api.TechnicalAskRequest(
            vraag="standaard skirtboard widths",
            source_code="CEMA_BELT_CONVEYORS_7",
            use_rag=True,
            limit=5,
        )

        response = hybrid_api.technical_assistant_ask(
            payload
        )

        self.assertEqual(
            response["status"],
            "ok",
        )

        self.assertEqual(
            response["technical_context"],
            sql_context(),
        )

        self.assertEqual(
            response["rag_context"]["status"],
            "error",
        )

        self.assertEqual(
            response["rag_context"]["context_hits"],
            [],
        )

        self.assertEqual(
            response["rag_context"]["used_context"],
            [],
        )

        self.assertEqual(
            response["rag_context"]["scope_doc_ids"],
            [
                "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
            ],
        )


    @patch(
        "app.routers.hybrid_api._post_internal"
    )
    @patch(
        "app.routers.hybrid_api.get_technical_context"
    )
    def test_generic_technical_rag_uses_exact_19_doc_corpus(
        self,
        mock_sql,
        mock_post,
    ):
        mock_sql.return_value = {
            "status": "ok",
            "count": 1,
            "results": [],
        }

        mock_post.return_value = {
            "status": "ok",
            "context_hits": [],
            "used_context": [],
        }

        payload = hybrid_api.TechnicalAskRequest(
            vraag=(
                "Welke technische richtlijnen zijn "
                "beschikbaar voor transportbanden?"
            ),
            use_rag=True,
            limit=5,
        )

        response = hybrid_api.technical_assistant_ask(
            payload
        )

        mock_post.assert_called_once()

        _, kwargs = mock_post.call_args

        body = kwargs["json_body"]

        doc_ids = body["doc_ids"]

        self.assertEqual(
            len(doc_ids),
            19,
        )

        self.assertEqual(
            len(set(doc_ids)),
            19,
        )

        self.assertEqual(
            doc_ids,
            hybrid_api._technical_rag_doc_ids(
                None
            ),
        )

        self.assertEqual(
            response["rag_context"]["scope_doc_ids"],
            doc_ids,
        )


if __name__ == "__main__":
    unittest.main()
