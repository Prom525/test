import psycopg2
from psycopg2.extras import Json

POSTGRES = {
    "host": "localhost",
    "port": 15432,
    "dbname": "promati",
    "user": "postgres",
    "password": "SterkWachtwoord123",
}

SOURCE_CODE = "CEMA_BELT_CONVEYORS_7"


def table_exists(cur, source_code, table_title, page_no):
    cur.execute(
        """
        SELECT 1
        FROM technical_table
        WHERE source_code = %s
          AND table_title = %s
          AND page_no = %s
        LIMIT 1
        """,
        (source_code, table_title, page_no),
    )
    return cur.fetchone() is not None


def main():
    conn = psycopg2.connect(**POSTGRES)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    candidate_id,
                    source_code,
                    page_no,
                    topic_group,
                    table_title,
                    columns_json,
                    rows_json,
                    possible_canonical_key
                FROM technical_table_candidate
                WHERE source_code = %s
                  AND match_status = 'approved_candidate'
                ORDER BY page_no, candidate_id
                """,
                (SOURCE_CODE,),
            )

            candidates = cur.fetchall()
            promoted = 0
            skipped = 0

            for (
                candidate_id,
                source_code,
                page_no,
                topic_group,
                table_title,
                columns_json,
                rows_json,
                possible_canonical_key,
            ) in candidates:

                if table_exists(cur, source_code, table_title, page_no):
                    print(f"BESTAAT AL: candidate {candidate_id} - {table_title}")
                    skipped += 1
                    continue

                summary_nl = (
                    f"CEMA tabel uit {source_code}, PDF-pagina {page_no}. "
                    f"Geëxtraheerd via pdfplumber en handmatig als kandidaat goedgekeurd. "
                    f"Gebruik voorlopig als referentie-/lookup-tabel."
                )

                search_text = (
                    f"{table_title} {topic_group} "
                    f"{possible_canonical_key or ''} CEMA belt conveyor"
                )

                cur.execute(
                    """
                    INSERT INTO technical_table
                      (
                        source_code,
                        section_id,
                        table_title,
                        page_no,
                        topic_group,
                        table_type,
                        columns_json,
                        rows_json,
                        summary_nl,
                        search_text,
                        review_status,
                        review_note,
                        usable_for_calculation,
                        canonical_key
                      )
                    VALUES
                      (
                        %s,
                        NULL,
                        %s,
                        %s,
                        %s,
                        'reference_or_lookup_table',
                        %s,
                        %s,
                        %s,
                        %s,
                        'approved',
                        %s,
                        false,
                        %s
                      )
                    RETURNING table_id
                    """,
                    (
                        source_code,
                        table_title,
                        page_no,
                        topic_group,
                        Json(columns_json),
                        Json(rows_json),
                        summary_nl,
                        search_text,
                        f"Gecontroleerd vanuit technical_table_candidate candidate_id={candidate_id}. "
                        f"Nog niet vrijgegeven voor automatische berekening.",
                        possible_canonical_key,
                    ),
                )

                table_id = cur.fetchone()[0]

                cur.execute(
                    """
                    UPDATE technical_table_candidate
                    SET match_status = 'promoted',
                        review_note = %s
                    WHERE candidate_id = %s
                    """,
                    (
                        f"Gepropageerd naar technical_table.table_id={table_id}.",
                        candidate_id,
                    ),
                )

                print(f"PROMOTED: candidate {candidate_id} -> table_id {table_id} | {table_title}")
                promoted += 1

            conn.commit()
            print(f"\nKlaar. Promoted: {promoted}, overgeslagen: {skipped}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()