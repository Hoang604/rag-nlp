CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    path LTREE NOT NULL UNIQUE,
    verbatim_text TEXT NOT NULL,
    contextualized_text TEXT NOT NULL,
    start_line INT NOT NULL,
    end_line INT NOT NULL,
    context_type VARCHAR(32) NOT NULL,
    is_all_refs_resolved BOOLEAN NOT NULL,
    embedding VECTOR(512),
    tsv_content TSVECTOR,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_chunks_line_spans CHECK (end_line >= start_line AND start_line >= 1),
    CONSTRAINT chk_chunks_context_type CHECK (context_type IN ('SELF_CONTAINED', 'REQUIRES_EXTERNAL_CONTEXT')),
    CONSTRAINT chk_chunks_self_contained_resolved CHECK (context_type != 'SELF_CONTAINED' OR is_all_refs_resolved = TRUE)
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
CREATE INDEX IF NOT EXISTS idx_chunks_context_type ON chunks (context_type, is_all_refs_resolved);

-- Trigger FTS: Duy trì search vector kỹ thuật từ text, không can thiệp logic nghiệp vụ
CREATE OR REPLACE FUNCTION update_chunks_tsv() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.tsv_content := 
        setweight(to_tsvector('simple', COALESCE(NEW.contextualized_text, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.verbatim_text, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_tsv_update ON chunks;
CREATE TRIGGER trg_chunks_tsv_update
BEFORE INSERT OR UPDATE OF contextualized_text, verbatim_text ON chunks
FOR EACH ROW EXECUTE FUNCTION update_chunks_tsv();

-- Trigger Assert: Kiểm tra cờ is_all_refs_resolved trên bảng chunks (Admit or Reject)
-- KHÔNG tự sửa đè giá trị của caller. Nếu caller khai man trạng thái so với thực tế -> REJECT NGAY LẬP TỨC.
CREATE OR REPLACE FUNCTION assert_chunk_invariants()
RETURNS TRIGGER AS $$
DECLARE
    total_refs INT;
    unattached_refs INT;
BEGIN
    IF NEW.context_type = 'SELF_CONTAINED' THEN
        IF NEW.is_all_refs_resolved != TRUE THEN
            RAISE EXCEPTION 'Vi phạm toàn vẹn: Chunk % là SELF_CONTAINED nhưng lại khai báo is_all_refs_resolved = FALSE.', NEW.id;
        END IF;
    ELSIF NEW.context_type = 'REQUIRES_EXTERNAL_CONTEXT' THEN
        IF TG_OP = 'INSERT' THEN
            IF NEW.is_all_refs_resolved = TRUE THEN
                RAISE EXCEPTION 'Vi phạm toàn vẹn: Chunk % là REQUIRES_EXTERNAL_CONTEXT khi mới tạo chưa có tham chiếu nào được giải quyết, không thể khai báo is_all_refs_resolved = TRUE.', NEW.id;
            END IF;
        ELSIF TG_OP = 'UPDATE' THEN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chunk_context_refs') THEN
                SELECT COUNT(*), COUNT(*) FILTER (WHERE target_chunk_id IS NULL OR edge_id IS NULL)
                INTO total_refs, unattached_refs
                FROM chunk_context_refs WHERE chunk_id = NEW.id;

                IF NEW.is_all_refs_resolved = TRUE AND (total_refs = 0 OR unattached_refs > 0) THEN
                    RAISE EXCEPTION 'Khai man trạng thái: Chunk % khai báo is_all_refs_resolved = TRUE nhưng thực tế có % ref và % ref chưa được gắn đầy đủ.',
                        NEW.id, total_refs, unattached_refs;
                ELSIF NEW.is_all_refs_resolved = FALSE AND (total_refs > 0 AND unattached_refs = 0) THEN
                    RAISE EXCEPTION 'Khai man trạng thái: Chunk % khai báo is_all_refs_resolved = FALSE nhưng thực tế toàn bộ % ref đều đã được gắn.',
                        NEW.id, total_refs;
                END IF;
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_assert_chunk_invariants ON chunks;
CREATE TRIGGER trg_assert_chunk_invariants
BEFORE INSERT OR UPDATE OF context_type, is_all_refs_resolved ON chunks
FOR EACH ROW EXECUTE FUNCTION assert_chunk_invariants();
