INSERT INTO rfq.supplier (
    supplier_name,
    supplier_norm,
    categories,
    specialties,
    country,
    notes
)
VALUES
(
    'Supplier OEM Trommels A',
    rfq.norm_txt('Supplier OEM Trommels A'),
    ARRAY['TROMMEL', 'ROL'],
    ARRAY['OEM', 'prijsgericht', 'standaard trommels'],
    'NL',
    'Startwaarde. Vervang door echte leverancier.'
),
(
    'Supplier Premium Bulk B',
    rfq.norm_txt('Supplier Premium Bulk B'),
    ARRAY['TROMMEL', 'ROL', 'IDLER'],
    ARRAY['PREMIUM', 'heavy-duty', 'documentatie', 'FAT'],
    'DE',
    'Startwaarde. Vervang door echte leverancier.'
),
(
    'Supplier Rollen C',
    rfq.norm_txt('Supplier Rollen C'),
    ARRAY['ROL', 'IDLER'],
    ARRAY['rollen', 'snelle levering', 'standaard'],
    'NL',
    'Startwaarde. Vervang door echte leverancier.'
)
ON CONFLICT (supplier_norm) DO NOTHING;

INSERT INTO rfq.supplier_score (
    supplier_id,
    oem_score,
    premium_score,
    price_score,
    delivery_score,
    quality_score,
    documentation_score,
    response_score
)
SELECT
    supplier_id,
    CASE
        WHEN supplier_name ILIKE '%OEM%' THEN 85
        ELSE 55
    END AS oem_score,
    CASE
        WHEN supplier_name ILIKE '%Premium%' THEN 90
        ELSE 50
    END AS premium_score,
    CASE
        WHEN supplier_name ILIKE '%OEM%' THEN 85
        ELSE 60
    END AS price_score,
    CASE
        WHEN supplier_name ILIKE '%Rollen%' THEN 80
        ELSE 65
    END AS delivery_score,
    CASE
        WHEN supplier_name ILIKE '%Premium%' THEN 90
        ELSE 65
    END AS quality_score,
    CASE
        WHEN supplier_name ILIKE '%Premium%' THEN 90
        ELSE 50
    END AS documentation_score,
    70 AS response_score
FROM rfq.supplier
ON CONFLICT (supplier_id) DO UPDATE SET
    oem_score = EXCLUDED.oem_score,
    premium_score = EXCLUDED.premium_score,
    price_score = EXCLUDED.price_score,
    delivery_score = EXCLUDED.delivery_score,
    quality_score = EXCLUDED.quality_score,
    documentation_score = EXCLUDED.documentation_score,
    response_score = EXCLUDED.response_score,
    updated_at = now();