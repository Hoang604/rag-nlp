-- 010_graph_edge_log_audit.sql: Immutable append-only audit log for knowledge graph curation

CREATE TABLE IF NOT EXISTS graph_edge_log (
    id UUID PRIMARY KEY,
    action VARCHAR(16) NOT NULL CHECK (action IN ('ADDED', 'REMOVED')),
    source_path LTREE NOT NULL,
    target_path LTREE NOT NULL,
    relation_type VARCHAR(32) NOT NULL REFERENCES relation_types(code),
    citation_text TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_graph_edge_log_source ON graph_edge_log USING gist(source_path);
CREATE INDEX IF NOT EXISTS idx_graph_edge_log_target ON graph_edge_log USING gist(target_path);
CREATE INDEX IF NOT EXISTS idx_graph_edge_log_created_at ON graph_edge_log (created_at DESC);
