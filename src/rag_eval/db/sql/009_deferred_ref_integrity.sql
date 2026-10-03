-- Migration 009: Chuyển đổi ràng buộc toàn vẹn cạnh tham chiếu sang Constraint Trigger hoãn lại (DEFERRED)
-- Khắc phục DEF-INGEST-017: Tránh lỗi kiểm tra tức thì khi PostgreSQL thực thi FK cascade ON DELETE SET NULL

-- 1. Xóa bỏ CHECK constraint tức thời trên bảng chunk_context_refs
ALTER TABLE chunk_context_refs DROP CONSTRAINT IF EXISTS chk_ref_edge_integrity;

-- 2. Tạo hàm kiểm tra toàn vẹn cạnh tham chiếu hoãn lại
CREATE OR REPLACE FUNCTION assert_chunk_ref_edge_integrity()
RETURNS TRIGGER AS $$
BEGIN
    -- Kiểm tra ở thời điểm commit giao dịch:
    -- target_chunk_id và edge_id phải cùng có giá trị (đã gắn kết) hoặc cùng NULL (chưa gắn kết / đã cascade xóa)
    IF (NEW.target_chunk_id IS NULL AND NEW.edge_id IS NOT NULL)
       OR (NEW.target_chunk_id IS NOT NULL AND NEW.edge_id IS NULL) THEN
        RAISE EXCEPTION 'Bất nhất toàn vẹn ref: target_chunk_id (%) và edge_id (%) phải cùng có giá trị hoặc cùng NULL.',
            NEW.target_chunk_id, NEW.edge_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Tạo CONSTRAINT TRIGGER hoãn lại đến cuối giao dịch (DEFERRABLE INITIALLY DEFERRED)
DROP TRIGGER IF EXISTS trg_assert_chunk_ref_edge_integrity ON chunk_context_refs;
CREATE CONSTRAINT TRIGGER trg_assert_chunk_ref_edge_integrity
AFTER INSERT OR UPDATE ON chunk_context_refs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION assert_chunk_ref_edge_integrity();

-- 4. Cập nhật hàm assert_chunk_context_ref_invariants để hỗ trợ cascading an toàn
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

        -- Nếu cạnh còn tồn tại trong graph_edges, xác thực tính khớp 1:1 với ref
        IF e_source IS NOT NULL THEN
            IF e_source != NEW.chunk_id OR e_target IS DISTINCT FROM NEW.target_chunk_id THEN
                RAISE EXCEPTION 'Bất nhất dữ liệu đồ thị: Cạnh edge_id % (source: %, target: %) không khớp với ref (source: %, target: %).',
                    NEW.edge_id, e_source, e_target, NEW.chunk_id, NEW.target_chunk_id;
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
