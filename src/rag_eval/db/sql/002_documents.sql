CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_slug VARCHAR(255) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    raw_text TEXT,
    valid_from DATE,
    valid_to DATE,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_documents_dates CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX IF NOT EXISTS idx_documents_slug ON documents (doc_slug);
CREATE INDEX IF NOT EXISTS idx_documents_dates ON documents (valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin (metadata jsonb_path_ops);
