CREATE TABLE IF NOT EXISTS graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    target_chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL REFERENCES relation_types(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_graph_edges_no_self_loop CHECK (target_chunk_id != source_chunk_id),
    CONSTRAINT uq_graph_edges UNIQUE (source_chunk_id, target_chunk_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges (source_chunk_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges (target_chunk_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_relation ON graph_edges (relation_type);
