BEGIN;

-- =========================================================
-- BASELINE
-- =========================================================

CREATE TEMP TABLE _prov_patch_baseline AS
SELECT
    (SELECT COUNT(*)::bigint
     FROM public.vw_sb_excel_checks) AS checks_rows,

    (SELECT COUNT(*)::bigint
     FROM public.vw_fact_inspection_excel_v2) AS fact_rows;


-- =========================================================
-- 1. vw_sb_excel_checks
--
-- Bestaande 17 kolommen blijven exact gelijk.
-- section_idx + row_nr worden alleen achteraan toegevoegd.
-- =========================================================

CREATE OR REPLACE VIEW public.vw_sb_excel_checks AS

WITH unpivot AS (
    SELECT
        b.inspection_key,
        b.inspected_on,
        b.lijn_code,
        b.title,
        b.source_file,
        b.locatie_raw,
        b.band_code,
        b.scraper_type_raw,
        b.band_width_effective_mm AS band_width_mm,
        b.meshoogte_mm,
        b.meshoogte_code,
        b.mes_vervangen,
        b.competitor_hosch,
        b.commentaar,

        x.check_code,
        x.raw_value,

        -- provenance
        b.section_idx,
        b.row_nr

    FROM public.vw_sb_excel_item_base b

    CROSS JOIN LATERAL (
        VALUES
            ('vervuiling_onder_band'::text,     b.col_3),
            ('band_loop_tov_trommels'::text,    b.col_4),
            ('band_algemene_staat'::text,       b.col_5),
            ('afdichting_stortpunt'::text,       b.col_6),
            ('werking_schrapers'::text,          b.col_7)
    ) x(check_code, raw_value)
)

SELECT
    inspection_key,
    inspected_on,
    lijn_code,
    title,
    source_file,
    locatie_raw,
    band_code,
    scraper_type_raw,
    band_width_mm,
    meshoogte_mm,
    meshoogte_code,
    mes_vervangen,
    competitor_hosch,
    commentaar,
    check_code,

    CASE
        WHEN upper(trim(raw_value)) = 'X'
            THEN 'DONE'::text
        ELSE upper(trim(raw_value))
    END AS status,

    raw_value,

    -- nieuwe kolommen, append-only
    section_idx,
    row_nr

FROM unpivot

WHERE NULLIF(
    trim(COALESCE(raw_value, '')),
    ''
) IS NOT NULL;


-- =========================================================
-- 2. vw_fact_inspection_excel_v2
--
-- Bestaande 16 kolommen blijven exact gelijk.
-- section_idx + row_nr worden alleen achteraan toegevoegd.
-- =========================================================

CREATE OR REPLACE VIEW public.vw_fact_inspection_excel_v2 AS

SELECT
    inspection_key,
    inspected_on AS document_date,
    lijn_code AS line_hint,
    band_code,
    locatie_raw,
    scraper_type_raw,
    band_width_mm,
    meshoogte_mm,
    meshoogte_code,
    mes_vervangen,
    competitor_hosch,
    commentaar,
    check_code,
    status,
    source_file,
    'excel'::text AS source_system,

    -- nieuwe provenancevelden
    section_idx,
    row_nr

FROM public.vw_sb_excel_checks

WHERE check_code = ANY (
    ARRAY[
        'vervuiling_onder_band'::text,
        'band_loop_tov_trommels'::text,
        'afdichting_stortpunt'::text,
        'werking_schrapers'::text
    ]
);


-- =========================================================
-- 3. HARDE VALIDATIE
-- =========================================================

DO $$
DECLARE
    baseline_checks bigint;
    baseline_fact bigint;

    actual_checks bigint;
    actual_fact bigint;

    checks_distinct bigint;
    fact_distinct bigint;

    checks_null_keys bigint;
    fact_null_keys bigint;

    expected_fact_from_checks bigint;

    checks_cols text[];
    fact_cols text[];
BEGIN

    SELECT
        checks_rows,
        fact_rows
    INTO
        baseline_checks,
        baseline_fact
    FROM _prov_patch_baseline;


    -- -----------------------------------------------------
    -- Rowcounts mogen absoluut niet veranderen
    -- -----------------------------------------------------

    SELECT COUNT(*)::bigint
    INTO actual_checks
    FROM public.vw_sb_excel_checks;

    SELECT COUNT(*)::bigint
    INTO actual_fact
    FROM public.vw_fact_inspection_excel_v2;


    IF actual_checks <> baseline_checks THEN
        RAISE EXCEPTION
            'checks rowcount gewijzigd: voor=%, na=%',
            baseline_checks,
            actual_checks;
    END IF;

    IF actual_fact <> baseline_fact THEN
        RAISE EXCEPTION
            'fact rowcount gewijzigd: voor=%, na=%',
            baseline_fact,
            actual_fact;
    END IF;


    -- -----------------------------------------------------
    -- Kolomvolgorde exact controleren
    -- -----------------------------------------------------

    SELECT array_agg(
        column_name
        ORDER BY ordinal_position
    )
    INTO checks_cols
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'vw_sb_excel_checks';


    IF checks_cols <> ARRAY[
        'inspection_key',
        'inspected_on',
        'lijn_code',
        'title',
        'source_file',
        'locatie_raw',
        'band_code',
        'scraper_type_raw',
        'band_width_mm',
        'meshoogte_mm',
        'meshoogte_code',
        'mes_vervangen',
        'competitor_hosch',
        'commentaar',
        'check_code',
        'status',
        'raw_value',
        'section_idx',
        'row_nr'
    ]::text[] THEN
        RAISE EXCEPTION
            'Onverwachte checks kolomvolgorde: %',
            checks_cols;
    END IF;


    SELECT array_agg(
        column_name
        ORDER BY ordinal_position
    )
    INTO fact_cols
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'vw_fact_inspection_excel_v2';


    IF fact_cols <> ARRAY[
        'inspection_key',
        'document_date',
        'line_hint',
        'band_code',
        'locatie_raw',
        'scraper_type_raw',
        'band_width_mm',
        'meshoogte_mm',
        'meshoogte_code',
        'mes_vervangen',
        'competitor_hosch',
        'commentaar',
        'check_code',
        'status',
        'source_file',
        'source_system',
        'section_idx',
        'row_nr'
    ]::text[] THEN
        RAISE EXCEPTION
            'Onverwachte fact kolomvolgorde: %',
            fact_cols;
    END IF;


    -- -----------------------------------------------------
    -- Nieuwe provenance-key moet volledig en uniek zijn
    --
    -- check-key:
    -- inspection_key + section_idx + row_nr + check_code
    -- -----------------------------------------------------

    SELECT
        COUNT(DISTINCT (
            inspection_key,
            section_idx,
            row_nr,
            check_code
        ))::bigint,

        COUNT(*) FILTER (
            WHERE inspection_key IS NULL
               OR section_idx IS NULL
               OR row_nr IS NULL
               OR check_code IS NULL
        )::bigint

    INTO
        checks_distinct,
        checks_null_keys

    FROM public.vw_sb_excel_checks;


    IF checks_distinct <> actual_checks THEN
        RAISE EXCEPTION
            'checks provenance niet uniek: rows=%, distinct=%',
            actual_checks,
            checks_distinct;
    END IF;

    IF checks_null_keys <> 0 THEN
        RAISE EXCEPTION
            'checks bevat % null provenance keys',
            checks_null_keys;
    END IF;


    SELECT
        COUNT(DISTINCT (
            inspection_key,
            section_idx,
            row_nr,
            check_code
        ))::bigint,

        COUNT(*) FILTER (
            WHERE inspection_key IS NULL
               OR section_idx IS NULL
               OR row_nr IS NULL
               OR check_code IS NULL
        )::bigint

    INTO
        fact_distinct,
        fact_null_keys

    FROM public.vw_fact_inspection_excel_v2;


    IF fact_distinct <> actual_fact THEN
        RAISE EXCEPTION
            'fact provenance niet uniek: rows=%, distinct=%',
            actual_fact,
            fact_distinct;
    END IF;

    IF fact_null_keys <> 0 THEN
        RAISE EXCEPTION
            'fact bevat % null provenance keys',
            fact_null_keys;
    END IF;


    -- -----------------------------------------------------
    -- Fact moet exact de vier toegestane checktypes bevatten
    -- -----------------------------------------------------

    SELECT COUNT(*)::bigint
    INTO expected_fact_from_checks
    FROM public.vw_sb_excel_checks
    WHERE check_code = ANY (
        ARRAY[
            'vervuiling_onder_band',
            'band_loop_tov_trommels',
            'afdichting_stortpunt',
            'werking_schrapers'
        ]
    );


    IF expected_fact_from_checks <> actual_fact THEN
        RAISE EXCEPTION
            'checks->fact filter mismatch: verwacht=%, fact=%',
            expected_fact_from_checks,
            actual_fact;
    END IF;


    RAISE NOTICE
        'VALIDATED: checks=% fact=% checks_distinct=% fact_distinct=%',
        actual_checks,
        actual_fact,
        checks_distinct,
        fact_distinct;

END
$$;


-- =========================================================
-- 4. RESULTAAT TONEN
-- =========================================================

SELECT
    'vw_sb_excel_checks' AS object_name,
    COUNT(*)::bigint AS rows_total,
    COUNT(DISTINCT (
        inspection_key,
        section_idx,
        row_nr,
        check_code
    ))::bigint AS distinct_provenance_keys,
    COUNT(*) FILTER (
        WHERE section_idx IS NULL
           OR row_nr IS NULL
    )::bigint AS null_provenance
FROM public.vw_sb_excel_checks

UNION ALL

SELECT
    'vw_fact_inspection_excel_v2',
    COUNT(*)::bigint,
    COUNT(DISTINCT (
        inspection_key,
        section_idx,
        row_nr,
        check_code
    ))::bigint,
    COUNT(*) FILTER (
        WHERE section_idx IS NULL
           OR row_nr IS NULL
    )::bigint
FROM public.vw_fact_inspection_excel_v2;


SELECT
    check_code,
    COUNT(*)::bigint AS checks_rows,
    COUNT(*) FILTER (
        WHERE check_code <> 'band_algemene_staat'
    )::bigint AS fact_eligible
FROM public.vw_sb_excel_checks
GROUP BY check_code
ORDER BY check_code;


COMMIT;