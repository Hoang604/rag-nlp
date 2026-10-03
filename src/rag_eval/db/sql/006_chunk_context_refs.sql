CREATE TABLE IF NOT EXISTS chunk_context_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    char_start INT,
    char_end INT,
    target_chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    edge_id UUID REFERENCES graph_edges(id) ON DELETE SET NULL,
    is_attached BOOLEAN GENERATED ALWAYS AS (target_chunk_id IS NOT NULL) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_ref_span_geometry CHECK (
        (char_start IS NULL AND char_end IS NULL)
        OR
        (char_start IS NOT NULL AND char_end IS NOT NULL AND char_end > char_start AND char_start >= 0)
    ),
    CONSTRAINT chk_ref_no_self_loop CHECK (target_chunk_id IS NULL OR target_chunk_id != chunk_id),
    CONSTRAINT chk_ref_edge_integrity CHECK (
        (target_chunk_id IS NULL AND edge_id IS NULL)
        OR
        (target_chunk_id IS NOT NULL AND edge_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_chunk_refs_chunk_id ON chunk_context_refs (chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_refs_target_id ON chunk_context_refs (target_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_refs_edge_id ON chunk_context_refs (edge_id);

-- TRIGGER VALIDATION: Kiểm tra tính toàn vẹn của tham chiếu ngữ cảnh (Admit or Reject)
CREATE OR REPLACE FUNCTION assert_chunk_context_ref_invariants()
RETURNS TRIGGER AS $$
DECLARE
    e_source UUID;
    e_target UUID;
    c_type VARCHAR(32);
BEGIN
    SELECT context_type INTO c_type FROM chunks WHERE id = NEW.chunk_id;
    IF c_type = 'SELF_CONTAINED' THEN
        RAISE EXCEPTION 'Vi phạm toàn vẹn: Chunk % được khai báo là SELF_CONTAINED, không được phép gán tham chiếu ngoại vi.', NEW.chunk_id;
    END IF;

    IF NEW.edge_id IS NOT NULL THEN
        SELECT source_chunk_id, target_chunk_id INTO e_source, e_target
        FROM graph_edges WHERE id = NEW.edge_id;

        IF e_source IS NULL THEN
            RAISE EXCEPTION 'Vi phạm toàn vẹn: Cạnh đồ thị edge_id % không tồn tại trong graph_edges.', NEW.edge_id;
        END IF;

        IF e_source != NEW.chunk_id OR e_target IS DISTINCT FROM NEW.target_chunk_id THEN
            RAISE EXCEPTION 'Bất nhất dữ liệu đồ thị: Cạnh edge_id % (source: %, target: %) không khớp với ref (source: %, target: %).',
                NEW.edge_id, e_source, e_target, NEW.chunk_id, NEW.target_chunk_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_assert_chunk_context_ref ON chunk_context_refs;
CREATE TRIGGER trg_assert_chunk_context_ref
BEFORE INSERT OR UPDATE ON chunk_context_refs
FOR EACH ROW EXECUTE FUNCTION assert_chunk_context_ref_invariants();

-- TRIGGER VALIDATION: Ràng buộc nhất quán tại Transaction Boundary
CREATE OR REPLACE FUNCTION assert_chunk_ref_consistency()
RETURNS TRIGGER AS $$
DECLARE
    target_cid UUID := COALESCE(NEW.chunk_id, OLD.chunk_id);
    c_type VARCHAR(32);
    c_resolved BOOLEAN;
    total_refs INT;
    unattached_refs INT;
BEGIN
    SELECT context_type, is_all_refs_resolved 
    INTO c_type, c_resolved 
    FROM chunks WHERE id = target_cid;

    IF c_type IS NULL THEN
        RETURN NULL;
    END IF;

    IF c_type = 'SELF_CONTAINED' THEN
        SELECT COUNT(*) INTO total_refs FROM chunk_context_refs WHERE chunk_id = target_cid;
        IF total_refs > 0 THEN
            RAISE EXCEPTION 'Bất nhất dữ liệu: Chunk % là SELF_CONTAINED nhưng lại tồn tại % ref trong chunk_context_refs.', target_cid, total_refs;
        END IF;
    ELSIF c_type = 'REQUIRES_EXTERNAL_CONTEXT' THEN
        SELECT COUNT(*), COUNT(*) FILTER (WHERE target_chunk_id IS NULL OR edge_id IS NULL)
        INTO total_refs, unattached_refs
        FROM chunk_context_refs WHERE chunk_id = target_cid;

        IF c_resolved = TRUE AND (total_refs = 0 OR unattached_refs > 0) THEN
            RAISE EXCEPTION 'Bất nhất dữ liệu: Chunk % có is_all_refs_resolved = TRUE nhưng thực tế có % ref và % ref chưa được gắn. Caller phải cập nhật tường minh.',
                target_cid, total_refs, unattached_refs;
        ELSIF c_resolved = FALSE AND (total_refs > 0 AND unattached_refs = 0) THEN
            RAISE EXCEPTION 'Bất nhất dữ liệu: Toàn bộ % ref của Chunk % đã được gắn đầy đủ, nhưng is_all_refs_resolved vẫn là FALSE. Caller phải cập nhật tường minh.',
                total_refs, target_cid;
        END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_assert_chunk_ref_consistency ON chunk_context_refs;
CREATE CONSTRAINT TRIGGER trg_assert_chunk_ref_consistency
AFTER INSERT OR UPDATE OR DELETE ON chunk_context_refs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION assert_chunk_ref_consistency();
