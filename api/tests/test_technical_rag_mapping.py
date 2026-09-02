import unittest

from app.routers import hybrid_api


class TechnicalRagMappingTests(unittest.TestCase):

    def test_exact_cema_mapping(self):
        self.assertEqual(
            hybrid_api._technical_rag_doc_ids(
                "CEMA_BELT_CONVEYORS_7"
            ),
            [
                "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
            ],
        )

    def test_transportbandenboek_maps_to_ten_documents(self):
        self.assertEqual(
            hybrid_api._technical_rag_doc_ids(
                "TRANSPORTBANDENBOEK"
            ),
            [
                "1_schema_transportinstallatie",
                "2_bepaling_van_bandbreedte_en_bandsnelheid",
                "3_bepaling_van_het_motorvermogen_van_een_transportband",
                "4_bepaling_van_het_motorvermogen_van_een_transportband",
                "5_de_transporband_algemeen",
                "6_band_ondersteuning_tussen_de_eindtrommels",
                "7_aandrijving_aandrijftrommel_keertrommel_spantrommel",
                "8_bandreiniging_voorspanning_bandstabiliteit",
                "9_berekeningsvoorbeeld_transportband_met_rol_ondersteuning",
                "10_berekenings_voorbeeld_transportband_met_glij_ondersteuning",
            ],
        )

    def test_all_registered_book_sources(self):
        expected = {
            "MARTIN_SELECTING_BELT_CLEANER":
                ["selecting_the_right_belt_cleaner"],

            "MARTIN_BELT_ALIGNMENT":
                ["belt_alignment_ebook"],

            "MARTIN_TRANSFER_ZONES":
                ["transfer_point_zones_ebook"],

            "MARTIN_FOUNDATIONS_4":
                ["foundation_book"],

            "MARTIN_SAFETY_BOOK":
                ["l4049_safety_book"],

            "MARTIN_BELT_DAMAGE_13":
                ["13_types_ebook"],

            "CEMA_BELT_CONVEYORS_7":
                [
                    "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
                ],

            "DUNLOP_DESIGN":
                ["beltconveyordesign_dunlop"],

            "OFC_OPTIM_AUGE":
                ["ofc_optim_auge"],
        }

        for source_code, doc_ids in expected.items():
            with self.subTest(source_code=source_code):
                self.assertEqual(
                    hybrid_api._technical_rag_doc_ids(
                        source_code
                    ),
                    doc_ids,
                )

    def test_generic_corpus_contains_exactly_19_documents(self):
        doc_ids = hybrid_api._technical_rag_doc_ids(
            None
        )

        self.assertEqual(
            len(doc_ids),
            19,
        )

        self.assertEqual(
            len(set(doc_ids)),
            19,
        )

        self.assertIn(
            "cema_belt_conveyors_o_0000730_with_new_logo_ng_2",
            doc_ids,
        )

        self.assertIn(
            "ofc_optim_auge",
            doc_ids,
        )

        self.assertIn(
            "13_types_ebook",
            doc_ids,
        )

    def test_non_rag_internal_source_returns_empty_list(self):
        self.assertEqual(
            hybrid_api._technical_rag_doc_ids(
                "PROMATI_RFQ_TECHNICAL_STANDARDS"
            ),
            [],
        )

    def test_unknown_source_does_not_fall_back_to_all_books(self):
        self.assertEqual(
            hybrid_api._technical_rag_doc_ids(
                "DOES_NOT_EXIST"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
