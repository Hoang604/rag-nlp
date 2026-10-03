CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_slug VARCHAR(255) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    raw_text TEXT,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_slug ON documents (doc_slug);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin (metadata jsonb_path_ops);
