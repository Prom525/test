CREATE SCHEMA IF NOT EXISTS rfq;

CREATE TABLE IF NOT EXISTS rfq.artifact (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id UUID NOT NULL,
    position_id UUID NULL,
    artifact_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    object_key TEXT NOT NULL,
    content_type TEXT DEFAULT 'application/pdf',
    file_size_bytes BIGINT NULL,
    sha256 TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rfq_artifact_rfq_id
ON rfq.artifact (rfq_id);

CREATE INDEX IF NOT EXISTS idx_rfq_artifact_position_id
ON rfq.artifact (position_id);

CREATE INDEX IF NOT EXISTS idx_rfq_artifact_type
ON rfq.artifact (artifact_type);