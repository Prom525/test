import json
from pathlib import Path

import pdfplumber
import psycopg2


PDF = Path(r"C:\ai-platform\data\rag\kennis\CEMA_Belt-Conveyors_O-0000730-with-New-Logo-NG-2.pdf")

POSTGRES = {
    "host": "localhost",
    "port": 15432,
    "dbname": "promati",
    "user": "postgres",
    "password": "SterkWachtwoord123",
}

SOURCE_DOC_ID = "cema_belt_conveyors_o_0000730_with_new_logo_ng_2"
SOURCE_CODE = "CEMA_BELT_CONVEYORS_7"

TABLES = [
    {
        "page_no": 63,
        "table_index": 0,
        "table_title": "Table 3.3 Table of flowability",
        "topic_group": "cema_material_characteristics",
        "table_type": "reference_table",
        "possible_canonical_key": "material_flowability",
    },
    {
        "page_no": 112,
        "table_index": 0,
        "table_title": "Table 5.18 Suggested normal spacing of belt idlers",
        "topic_group": "cema_idlers",
        "table_type": "selection_table",
        "possible_canonical_key": "idler_spacing",
    },
    {
        "page_no": 126,
        "table_index": 0,
        "table_title": "Table 5.41 CEMA Class F idler ratings",
        "topic_group": "cema_idlers",
        "table_type": "rating_table",
        "possible_canonical_key": "idler_load_rating",
    },
    {
        "page_no": 126,
        "table_index": 1,
        "table_title": "Table 5.42 CEMA picking idler load ratings",
        "topic_group": "cema_idlers",
        "table_type": "rating_table",
        "possible_canonical_key": "idler_load_rating",
    },
    {
        "page_no": 138,
        "table_index": 0,
        "table_title": "Table 5.61 Average weight of single roll return idler rotating parts - steel rolls",
        "topic_group": "cema_idlers",
        "table_type": "reference_table",
        "possible_canonical_key": "idler_rotating_parts_weight",
    },
    {
        "page_no": 85,
        "table_index": 0,
        "table_title": "Table 4.22 CEMA standard skirtboard widths",
        "topic_group": "cema_capacity",
        "table_type": "reference_table",
        "possible_canonical_key": "cema_standard_skirtboard_widths",
    },
    {
        "page_no": 94,
        "table_index": 0,
        "table_title": "Table 4.41 CEMA standard area and capacity table - imperial flat belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 95,
        "table_index": 0,
        "table_title": "Table 4.42 CEMA standard area and capacity table - imperial troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 96,
        "table_index": 0,
        "table_title": "Table 4.43 CEMA standard area and capacity table - imperial troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 97,
        "table_index": 0,
        "table_title": "Table 4.44 CEMA standard area and capacity table - imperial troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 98,
        "table_index": 0,
        "table_title": "Table 4.45 CEMA standard area and capacity table - metric flat belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 99,
        "table_index": 0,
        "table_title": "Table 4.46 CEMA standard area and capacity table - metric troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 100,
        "table_index": 0,
        "table_title": "Table 4.47 CEMA standard area and capacity table - metric troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
    {
        "page_no": 101,
        "table_index": 0,
        "table_title": "Table 4.48 CEMA standard area and capacity table - metric troughed belt",
        "topic_group": "cema_capacity",
        "table_type": "capacity_table",
        "possible_canonical_key": "cema_standard_area_capacity",
    },
]


TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 5,
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 20,
    "min_words_vertical": 1,
    "min_words_horizontal": 1,
}


def clean_cell(value):
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def normalize_table(raw_table):
    """
    Bewaart tabel compact als:
    columns_json: kolommen c0, c1, ...
    rows_json: elke rij als dict met c0, c1...
    """
    max_cols = max(len(row) for row in raw_table if row) if raw_table else 0

    columns = [
        {"key": f"c{i}", "label": f"Kolom {i + 1}"}
        for i in range(max_cols)
    ]

    rows = []
    for row in raw_table:
        if not row:
            continue
        padded = list(row) + [""] * (max_cols - len(row))
        rows.append({f"c{i}": clean_cell(padded[i]) for i in range(max_cols)})

    return columns, rows


def candidate_exists(cur, page_no, table_title):
    cur.execute(
        """
        SELECT 1
        FROM technical_table_candidate
        WHERE source_doc_id = %s
          AND source_code = %s
          AND page_no = %s
          AND table_title = %s
        LIMIT 1
        """,
        (SOURCE_DOC_ID, SOURCE_CODE, page_no, table_title),
    )
    return cur.fetchone() is not None


def main():
    conn = psycopg2.connect(**POSTGRES)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO technical_extraction_run
                  (source_doc_id, source_code, extraction_type, status, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING run_id
                """,
                (
                    SOURCE_DOC_ID,
                    SOURCE_CODE,
                    "cema_table_candidate_pdfplumber",
                    "started",
                    "Gerichte CEMA tabel-extractie met pdfplumber voor zichtbare tabellen.",
                ),
            )
            run_id = cur.fetchone()[0]

            created = 0
            scanned = 0

            with pdfplumber.open(PDF) as pdf:
                for spec in TABLES:
                    scanned += 1
                    page_no = spec["page_no"]
                    table_index = spec["table_index"]
                    table_title = spec["table_title"]

                    page = pdf.pages[page_no - 1]
                    tables = page.extract_tables(TABLE_SETTINGS)

                    if table_index >= len(tables):
                        print(f"GEEN TABEL: pagina {page_no}, index {table_index}")
                        continue

                    raw_table = tables[table_index]
                    columns, rows = normalize_table(raw_table)

                    if candidate_exists(cur, page_no, table_title):
                        print(f"BESTAAT AL: {table_title}")
                        continue

                    raw_text = page.extract_text() or ""

                    cur.execute(
                        """
                        INSERT INTO technical_table_candidate
                          (
                            source_doc_id,
                            source_code,
                            chunk_index,
                            page_no,
                            topic_group,
                            table_title,
                            raw_text,
                            columns_json,
                            rows_json,
                            markdown_table,
                            possible_canonical_key,
                            match_status,
                            confidence,
                            review_note
                          )
                        VALUES
                          (%s, %s, NULL, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NULL, %s, 'candidate', %s, %s)
                        """,
                        (
                            SOURCE_DOC_ID,
                            SOURCE_CODE,
                            page_no,
                            spec["topic_group"],
                            table_title,
                            raw_text,
                            json.dumps(columns, ensure_ascii=False),
                            json.dumps(rows, ensure_ascii=False),
                            spec["possible_canonical_key"],
                            0.85,
                            "CEMA tabel automatisch geëxtraheerd met pdfplumber; handmatige review nodig.",
                        ),
                    )

                    created += 1
                    print(f"candidate gemaakt: {table_title}")

            cur.execute(
                """
                UPDATE technical_extraction_run
                SET status = 'completed',
                    chunks_scanned = %s,
                    candidates_created = %s,
                    updated_at = now()
                WHERE run_id = %s
                """,
                (scanned, created, run_id),
            )

            conn.commit()
            print(f"\nKlaar. Nieuwe CEMA table candidates: {created}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()