CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    path LTREE NOT NULL UNIQUE,
    verbatim_text TEXT NOT NULL,
    contextualized_text TEXT NOT NULL,
    start_line INT NOT NULL,
    end_line INT NOT NULL,
    embedding VECTOR(512),
    tsv_content TSVECTOR,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_chunks_line_spans CHECK (end_line >= start_line AND start_line >= 1)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_chunks_path_gist ON chunks USING gist (path);
CREATE INDEX IF NOT EXISTS idx_chunks_path_btree ON chunks (path);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING gin (tsv_content);
CREATE INDEX IF NOT EXISTS idx_chunks_verbatim_trgm ON chunks USING gin (verbatim_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_context_trgm ON chunks USING gin (contextualized_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING gin (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_line_spans ON chunks (document_id, start_line, end_line);

-- Trigger FTS: Duy trì search vector kỹ thuật từ contextualized_text
CREATE OR REPLACE FUNCTION update_chunks_tsv() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv_content := to_tsvector('simple', COALESCE(NEW.contextualized_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_tsv_update ON chunks;
CREATE TRIGGER trg_chunks_tsv_update
BEFORE INSERT OR UPDATE OF contextualized_text ON chunks
FOR EACH ROW EXECUTE FUNCTION update_chunks_tsv();
