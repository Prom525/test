CREATE SCHEMA IF NOT EXISTS rfq;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rfq.request (
    rfq_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    odoo_reference text NOT NULL,
    customer_name_internal text,
    customer_norm text,
    verkoper text,
    request_type text DEFAULT 'UNKNOWN',
    customer_type text DEFAULT 'UNKNOWN',
    selected_route text DEFAULT 'UNDECIDED',
    status text DEFAULT 'DRAFT',
    customer_value_score numeric,
    customer_context jsonb DEFAULT '{}'::jsonb,
    intake_summary jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.document (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    file_name text NOT NULL,
    document_type text DEFAULT 'DRAWING',
    file_hash_sha256 text,
    stored_path text,
    extracted_text text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.position (
    position_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    pos_nr text NOT NULL,
    drawing_mark text,
    product_type text DEFAULT 'UNKNOWN',
    quantity numeric DEFAULT 1,
    extracted_specs jsonb DEFAULT '{}'::jsonb,
    missing_fields jsonb DEFAULT '[]'::jsonb,
    confidence_score numeric,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.customer_requirement_memory (
    memory_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_norm text NOT NULL,
    requirement_type text NOT NULL,
    requirement_text text NOT NULL,
    source_odoo_reference text,
    source_rfq_id uuid,
    frequency_count integer DEFAULT 1,
    confidence_score numeric DEFAULT 50,
    active boolean DEFAULT true,
    first_seen_at timestamptz DEFAULT now(),
    last_seen_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.supplier (
    supplier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_name text NOT NULL,
    supplier_norm text NOT NULL UNIQUE,
    active boolean DEFAULT true,
    categories text[] DEFAULT '{}',
    specialties text[] DEFAULT '{}',
    country text,
    notes text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.supplier_score (
    supplier_id uuid PRIMARY KEY REFERENCES rfq.supplier(supplier_id) ON DELETE CASCADE,
    oem_score numeric DEFAULT 50,
    premium_score numeric DEFAULT 50,
    price_score numeric DEFAULT 50,
    delivery_score numeric DEFAULT 50,
    quality_score numeric DEFAULT 50,
    documentation_score numeric DEFAULT 50,
    response_score numeric DEFAULT 50,
    rfq_count integer DEFAULT 0,
    order_count integer DEFAULT 0,
    lost_count integer DEFAULT 0,
    conversion_rate numeric DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.decision_log (
    decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    step text NOT NULL,
    gpt_suggestion jsonb DEFAULT '{}'::jsonb,
    user_override jsonb DEFAULT '{}'::jsonb,
    final_decision jsonb DEFAULT '{}'::jsonb,
    approved_by text,
    approved_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.outcome (
    outcome_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    outcome text NOT NULL,
    loss_reason text,
    order_value numeric,
    margin_value numeric,
    supplier_id uuid,
    verkoper text,
    offer_effort_hours numeric,
    decided_at date,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq.pdf_output (
    pdf_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    template_version text NOT NULL,
    input_snapshot jsonb DEFAULT '{}'::jsonb,
    pdf_path text,
    pdf_hash_sha256 text,
    created_at timestamptz DEFAULT now()
);

CREATE OR REPLACE FUNCTION rfq.norm_txt(v text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT NULLIF(
        regexp_replace(
            upper(trim(coalesce(v, ''))),
            '\s+',
            ' ',
            'g'
        ),
        ''
    )
$$;

CREATE INDEX IF NOT EXISTS idx_rfq_request_odoo_reference
ON rfq.request(odoo_reference);

CREATE INDEX IF NOT EXISTS idx_rfq_request_customer_norm
ON rfq.request(customer_norm);

CREATE INDEX IF NOT EXISTS idx_rfq_position_rfq_id
ON rfq.position(rfq_id);

CREATE INDEX IF NOT EXISTS idx_rfq_memory_customer_norm
ON rfq.customer_requirement_memory(customer_norm);

CREATE INDEX IF NOT EXISTS idx_rfq_decision_log_rfq_id
ON rfq.decision_log(rfq_id);