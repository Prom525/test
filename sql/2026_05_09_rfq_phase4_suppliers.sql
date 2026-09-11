CREATE TABLE IF NOT EXISTS rfq.request_supplier (
    request_supplier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    supplier_id uuid REFERENCES rfq.supplier(supplier_id),
    selection_rank integer,
    selection_reason text,
    selected_by text,
    selected_at timestamptz DEFAULT now(),
    status text DEFAULT 'SELECTED',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rfq_request_supplier_rfq_id
ON rfq.request_supplier(rfq_id);

CREATE INDEX IF NOT EXISTS idx_rfq_request_supplier_supplier_id
ON rfq.request_supplier(supplier_id);

CREATE TABLE IF NOT EXISTS rfq.supplier_rfq_event (
    supplier_rfq_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id uuid REFERENCES rfq.request(rfq_id) ON DELETE CASCADE,
    supplier_id uuid REFERENCES rfq.supplier(supplier_id),
    event_type text NOT NULL,
    event_note text,
    offer_value numeric,
    order_value numeric,
    response_days numeric,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_supplier_rfq_event_supplier_id
ON rfq.supplier_rfq_event(supplier_id);

CREATE OR REPLACE VIEW rfq.vw_supplier_performance_v1 AS
SELECT
    s.supplier_id,
    s.supplier_name,
    s.supplier_norm,
    s.active,
    s.categories,
    s.specialties,

    COALESCE(sc.oem_score, 50) AS oem_score,
    COALESCE(sc.premium_score, 50) AS premium_score,
    COALESCE(sc.price_score, 50) AS price_score,
    COALESCE(sc.delivery_score, 50) AS delivery_score,
    COALESCE(sc.quality_score, 50) AS quality_score,
    COALESCE(sc.documentation_score, 50) AS documentation_score,
    COALESCE(sc.response_score, 50) AS response_score,

    COUNT(e.*) FILTER (WHERE e.event_type = 'RFQ_SENT') AS rfq_sent_count,
    COUNT(e.*) FILTER (WHERE e.event_type = 'QUOTE_RECEIVED') AS quote_received_count,
    COUNT(e.*) FILTER (WHERE e.event_type = 'ORDER_WON') AS order_won_count,
    COUNT(e.*) FILTER (WHERE e.event_type = 'LOST') AS lost_count,

    CASE
        WHEN COUNT(e.*) FILTER (WHERE e.event_type = 'RFQ_SENT') = 0 THEN 0
        ELSE ROUND(
            (
                COUNT(e.*) FILTER (WHERE e.event_type = 'ORDER_WON')::numeric
                /
                COUNT(e.*) FILTER (WHERE e.event_type = 'RFQ_SENT')::numeric
            ) * 100,
            1
        )
    END AS rfq_to_order_conversion,

    ROUND(AVG(e.response_days) FILTER (WHERE e.response_days IS NOT NULL)::numeric, 1) AS avg_response_days,

    MAX(e.created_at) AS last_event_at

FROM rfq.supplier s
LEFT JOIN rfq.supplier_score sc
    ON sc.supplier_id = s.supplier_id
LEFT JOIN rfq.supplier_rfq_event e
    ON e.supplier_id = s.supplier_id
GROUP BY
    s.supplier_id,
    s.supplier_name,
    s.supplier_norm,
    s.active,
    s.categories,
    s.specialties,
    sc.oem_score,
    sc.premium_score,
    sc.price_score,
    sc.delivery_score,
    sc.quality_score,
    sc.documentation_score,
    sc.response_score;