CREATE TABLE IF NOT EXISTS rfq.canonical_model (
    canonical_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid NOT NULL REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,

    model_version text NOT NULL DEFAULT 'RFQ-CANONICAL-001',

    customer_context jsonb DEFAULT '{}'::jsonb,
    conveyor_data jsonb DEFAULT '{}'::jsonb,
    engineering_requirements jsonb DEFAULT '{}'::jsonb,
    documentation_requirements jsonb DEFAULT '{}'::jsonb,
    commercial_strategy jsonb DEFAULT '{}'::jsonb,
    supplier_strategy jsonb DEFAULT '{}'::jsonb,
    position_summary jsonb DEFAULT '[]'::jsonb,

    missing_data jsonb DEFAULT '[]'::jsonb,
    assumptions jsonb DEFAULT '[]'::jsonb,
    warnings jsonb DEFAULT '[]'::jsonb,

    approved boolean DEFAULT false,
    approved_by text,
    approved_at timestamptz,

    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rfq_canonical_model_rfq_id
ON rfq.canonical_model(rfq_id);

CREATE OR REPLACE VIEW rfq.vw_rfq_canonical_latest AS
SELECT DISTINCT ON (cm.rfq_id)
    cm.*,
    r.odoo_reference,
    r.customer_type,
    r.selected_route,
    r.request_type,
    r.verkoper
FROM rfq.canonical_model cm
JOIN rfq.request r
    ON r.rfq_id = cm.rfq_id
ORDER BY cm.rfq_id, cm.created_at DESC;
