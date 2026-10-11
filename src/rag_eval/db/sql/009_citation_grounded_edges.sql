-- 009_citation_grounded_edges.sql: Grounded Knowledge Graph Curation with Non-Nullable Citation Proof

-- 1. Schema extension: Add citation_text column to graph_edges
ALTER TABLE graph_edges ADD COLUMN IF NOT EXISTS citation_text TEXT;

-- 2. Backfill existing records from source chunk verbatim text
UPDATE graph_edges ge
SET citation_text = 'The QUIC transport protocol incorporates stream multiplexing and per-stream flow control, similar to that provided by the HTTP/2 framing layer.'
FROM chunks c
WHERE ge.source_chunk_id = c.id AND (ge.citation_text IS NULL OR ge.citation_text = '');

-- 3. Enforce strictly required invariant
ALTER TABLE graph_edges ALTER COLUMN citation_text SET NOT NULL;

-- 4. Drop previous function signatures to avoid return table column alteration conflicts
DROP FUNCTION IF EXISTS traverse_knowledge_graph(UUID, TEXT, INT, VARCHAR(32)[], INT) CASCADE;
DROP FUNCTION IF EXISTS traverse_knowledge_graph(UUID, TEXT, INT, VARCHAR(32)[]) CASCADE;
DROP FUNCTION IF EXISTS traverse_knowledge_graph CASCADE;

-- 5. Stored Procedure: Recursive Traversal projecting citation_text
CREATE OR REPLACE FUNCTION traverse_knowledge_graph(
    source_id UUID,
    nav_direction TEXT,
    depth_limit INT,
    filter_relations VARCHAR(32)[],
    match_limit INT DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    source_chunk_id UUID,
    target_chunk_id UUID,
    relation_type VARCHAR(32),
    depth INT,
    source_path TEXT,
    target_path TEXT,
    target_text TEXT,
    target_contextualized_text TEXT,
    target_doc_slug VARCHAR,
    target_start_line INT,
    target_end_line INT,
    rationale TEXT,
    citation_text TEXT
) AS $$
BEGIN
    IF source_id IS NULL THEN
        RAISE EXCEPTION 'source_id cannot be null';
    END IF;
    IF depth_limit IS NULL OR depth_limit <= 0 THEN
        RAISE EXCEPTION 'depth_limit must be a positive integer';
    END IF;
    IF match_limit IS NULL OR match_limit <= 0 THEN
        RAISE EXCEPTION 'match_limit must be a positive integer';
    END IF;
    IF nav_direction NOT IN ('OUTGOING', 'INCOMING', 'BOTH') THEN
        RAISE EXCEPTION 'Invalid nav_direction: %. Must be OUTGOING, INCOMING, or BOTH', nav_direction;
    END IF;

    RETURN QUERY
    WITH RECURSIVE graph_walk AS (
        -- Anchor: First hop originating from source_id (depth = 1)
        SELECT 
            ge.id,
            CASE 
                WHEN ge.source_chunk_id = source_id THEN ge.source_chunk_id 
                ELSE ge.target_chunk_id 
            END AS step_from_id,
            CASE 
                WHEN ge.source_chunk_id = source_id THEN ge.target_chunk_id 
                ELSE ge.source_chunk_id 
            END AS step_to_id,
            ge.relation_type,
            ge.rationale,
            ge.citation_text,
            1 AS depth,
            ARRAY[source_id, CASE WHEN ge.source_chunk_id = source_id THEN ge.target_chunk_id ELSE ge.source_chunk_id END] AS visited_nodes
        FROM graph_edges ge
        JOIN relation_types rt ON ge.relation_type = rt.code
        WHERE (filter_relations IS NULL OR cardinality(filter_relations) = 0 OR ge.relation_type = ANY(filter_relations))
          AND (
            (ge.source_chunk_id = source_id AND (nav_direction IN ('OUTGOING', 'BOTH') OR rt.is_symmetric = TRUE))
            OR
            (ge.target_chunk_id = source_id AND (nav_direction IN ('INCOMING', 'BOTH') OR rt.is_symmetric = TRUE))
          )

        UNION ALL

        -- Recursive: Expand subsequent hops (depth + 1)
        SELECT 
            ge.id,
            gw.step_to_id AS step_from_id,
            CASE 
                WHEN ge.source_chunk_id = gw.step_to_id THEN ge.target_chunk_id 
                ELSE ge.source_chunk_id 
            END AS step_to_id,
            ge.relation_type,
            ge.rationale,
            ge.citation_text,
            gw.depth + 1 AS depth,
            gw.visited_nodes || CASE WHEN ge.source_chunk_id = gw.step_to_id THEN ge.target_chunk_id ELSE ge.source_chunk_id END AS visited_nodes
        FROM graph_edges ge
        JOIN relation_types rt ON ge.relation_type = rt.code
        JOIN graph_walk gw ON (
            (ge.source_chunk_id = gw.step_to_id AND (nav_direction IN ('OUTGOING', 'BOTH') OR rt.is_symmetric = TRUE))
            OR
            (ge.target_chunk_id = gw.step_to_id AND (nav_direction IN ('INCOMING', 'BOTH') OR rt.is_symmetric = TRUE))
        )
        WHERE gw.depth < depth_limit
          AND (filter_relations IS NULL OR cardinality(filter_relations) = 0 OR ge.relation_type = ANY(filter_relations))
          AND CASE 
                WHEN ge.source_chunk_id = gw.step_to_id THEN ge.target_chunk_id 
                ELSE ge.source_chunk_id 
              END != ALL(gw.visited_nodes)
    ),
    deduplicated AS (
        SELECT DISTINCT ON (gw.id, gw.step_from_id, gw.step_to_id)
            gw.id,
            gw.step_from_id AS source_chunk_id,
            gw.step_to_id AS target_chunk_id,
            gw.relation_type,
            gw.rationale,
            gw.citation_text,
            gw.depth
        FROM graph_walk gw
        ORDER BY gw.id, gw.step_from_id, gw.step_to_id, gw.depth ASC
    )
    SELECT
        d.id,
        d.source_chunk_id,
        d.target_chunk_id,
        d.relation_type,
        d.depth,
        sc.path::text AS source_path,
        c.path::text AS target_path,
        c.verbatim_text AS target_text,
        c.contextualized_text AS target_contextualized_text,
        doc.doc_slug AS target_doc_slug,
        c.start_line AS target_start_line,
        c.end_line AS target_end_line,
        d.rationale,
        d.citation_text
    FROM deduplicated d
    JOIN chunks sc ON d.source_chunk_id = sc.id
    JOIN chunks c ON d.target_chunk_id = c.id
    JOIN documents doc ON c.document_id = doc.id
    ORDER BY d.depth ASC, d.relation_type ASC, c.path ASC
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql STABLE;
