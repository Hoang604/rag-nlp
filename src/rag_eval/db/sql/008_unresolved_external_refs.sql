-- Migration 008: Thêm cột target_path cho chunk_context_refs để lưu trữ đường dẫn phụ thuộc ngoại vi chưa giải quyết
ALTER TABLE chunk_context_refs ADD COLUMN IF NOT EXISTS target_path VARCHAR(500);
