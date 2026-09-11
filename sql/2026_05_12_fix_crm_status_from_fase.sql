CREATE OR REPLACE VIEW crm.vw_crm_opportunity_base_v1 AS
WITH base AS (
    SELECT
        r.raw_id,
        r.batch_id,
        r.pipeline_type,
        r.source_file,
        r.row_nr,
        r.imported_at,
        r.raw_json ->> 'ID' AS odoo_id,
        r.raw_json ->> 'Verkoopkans' AS opportunity_name,
        r.raw_json ->> 'Klant' AS account_contact_raw,
        crm.extract_account_name(r.raw_json ->> 'Klant') AS account_name,
        crm.norm_txt(crm.extract_account_name(r.raw_json ->> 'Klant')) AS account_norm,
        COALESCE(
            NULLIF(r.raw_json ->> 'Naam contactpersoon', ''),
            crm.extract_contact_from_customer(r.raw_json ->> 'Klant')
        ) AS contact_name,
        r.raw_json ->> 'E-mail' AS email,
        r.raw_json ->> 'Verkoper' AS verkoper,
        r.raw_json ->> 'Fase' AS fase,
        r.raw_json ->> 'Verliesreden' AS verliesreden,
        crm.parse_date_any(r.raw_json ->> 'Aangemaakt op') AS aangemaakt_op,
        crm.parse_odoo_amount(r.raw_json ->> 'Verwachte omzet') AS verwachte_omzet,
        crm.parse_odoo_amount(r.raw_json ->> 'Pro rata omzet') AS pro_rata_omzet
    FROM crm.odoo_opportunity_raw r
)
SELECT
    b.raw_id,
    b.batch_id,
    b.pipeline_type,
    b.source_file,
    b.row_nr,
    b.imported_at,
    b.odoo_id,
    b.opportunity_name,
    b.account_contact_raw,
    b.account_name,
    b.account_norm,
    b.contact_name,
    b.email,
    b.verkoper,
    b.fase,
    b.verliesreden,
    b.aangemaakt_op,
    b.verwachte_omzet,
    b.pro_rata_omzet,

    CASE
        WHEN b.fase ILIKE '%Invoiced%' THEN 'GEFACTUREERD'
        WHEN b.fase ILIKE '%Won%' THEN 'GEWONNEN'
        WHEN b.pipeline_type = 'verloren' THEN 'VERLOREN'
        WHEN b.verliesreden IS NOT NULL AND TRIM(BOTH FROM b.verliesreden) <> '' THEN 'VERLOREN'
        ELSE 'OPEN'
    END AS status,

    CASE
        WHEN b.aangemaakt_op IS NULL THEN NULL::integer
        ELSE CURRENT_DATE - b.aangemaakt_op
    END AS dagen_open,

    COALESCE(ac.klanttype, 'UNKNOWN') AS klanttype,
    ac.sector,
    ac.strategic_tier,
    COALESCE(ac.is_key_account, false) AS is_key_account,
    ac.note AS account_note,

    CASE
        WHEN COALESCE(ac.klanttype, 'UNKNOWN') = 'ASSET_OWNER' THEN 30
        ELSE 0
    END +
    CASE
        WHEN COALESCE(ac.klanttype, 'UNKNOWN') = 'OEM' THEN 10
        ELSE 0
    END +
    CASE
        WHEN b.pipeline_type = 'huidig' THEN 20
        ELSE 0
    END +
    CASE
        WHEN b.verwachte_omzet >= 50000 THEN 15
        WHEN b.verwachte_omzet >= 10000 THEN 10
        WHEN b.verwachte_omzet > 0 THEN 5
        ELSE 0
    END +
    CASE
        WHEN b.aangemaakt_op IS NOT NULL AND (CURRENT_DATE - b.aangemaakt_op) <= 90 THEN 10
        WHEN b.aangemaakt_op IS NOT NULL AND (CURRENT_DATE - b.aangemaakt_op) <= 180 THEN 5
        ELSE 0
    END -
    CASE
        WHEN b.pipeline_type = 'verloren' THEN 25
        ELSE 0
    END AS kwaliteit_score,

    CASE
        WHEN COALESCE(ac.klanttype, 'UNKNOWN') = 'ASSET_OWNER' THEN 'Spoor 1 - Asset owner / premium performance'
        WHEN COALESCE(ac.klanttype, 'UNKNOWN') = 'OEM' THEN 'Spoor 2 - OEM / projectkanaal'
        WHEN COALESCE(ac.klanttype, 'UNKNOWN') = 'CONTRACTOR' THEN 'Projectmatig / contractor'
        ELSE 'Nog classificeren'
    END AS commercieel_spoor

FROM base b
LEFT JOIN crm.account_classification ac
    ON ac.account_norm = b.account_norm;