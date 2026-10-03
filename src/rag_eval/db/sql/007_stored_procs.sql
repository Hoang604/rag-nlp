-- 1. Stored Procedure: Recursive Knowledge Graph Traversal (Strict Contract)
-- Tối ưu hóa:
-- - Nhận diện quan hệ đối xứng (rt.is_symmetric = TRUE) để duyệt 2 chiều tự động.
-- - Chống chu trình lặp (visited_nodes) tránh loop vô hạn trên đồ thị có chu trình.
-- - Hỗ trợ lọc theo danh mục quan hệ (filter_relations).
-- - Tuyệt đối không dùng DEFAULT; validate tham số đầu vào (Fail-Fast).
CREATE OR REPLACE FUNCTION traverse_knowledge_graph(
    source_id UUID,
    nav_direction TEXT,
    depth_limit INT,
    filter_relations VARCHAR(32)[]
)
RETURNS TABLE (
    id UUID,
    source_chunk_id UUID,
    target_chunk_id UUID,
    relation_type VARCHAR(32),
    depth INT,
    target_path TEXT,
    target_text TEXT
) AS $$
BEGIN
    IF source_id IS NULL THEN
        RAISE EXCEPTION 'source_id cannot be null';
    END IF;
    IF depth_limit IS NULL OR depth_limit <= 0 THEN
        RAISE EXCEPTION 'depth_limit must be a positive integer';
    END IF;
    IF nav_direction NOT IN ('OUTGOING', 'INCOMING', 'BOTH') THEN
        RAISE EXCEPTION 'Invalid nav_direction: %. Must be OUTGOING, INCOMING, or BOTH', nav_direction;
    END IF;

    RETURN QUERY
    WITH RECURSIVE graph_walk AS (
        -- Anchor: Bước đầu tiên từ source_id (depth = 1)
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

        -- Recursive: Mở rộng các bước tiếp theo (depth + 1)
        SELECT 
            ge.id,
            gw.step_to_id AS step_from_id,
            CASE 
                WHEN ge.source_chunk_id = gw.step_to_id THEN ge.target_chunk_id 
                ELSE ge.source_chunk_id 
            END AS step_to_id,
            ge.relation_type,
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
        c.path::text AS target_path,
        c.verbatim_text AS target_text
    FROM deduplicated d
    LEFT JOIN chunks c ON d.target_chunk_id = c.id
    ORDER BY d.depth ASC, d.relation_type ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- 2. Stored Procedure: Exact & Trigram Grep Search (Strict Contract)
-- Tối ưu hóa:
-- - Bổ sung start_line, end_line cho phép grounding chính xác dòng trong tài liệu.
-- - Bổ sung lọc phân cấp cây tài liệu (path_prefix LTREE) qua index GiST.
-- - Bổ sung lọc trạng thái hoàn thiện ngữ cảnh (only_resolved BOOLEAN).
CREATE OR REPLACE FUNCTION verbatim_grep(
    query_pattern TEXT,
    target_documents TEXT[],
    path_prefix LTREE,
    only_resolved BOOLEAN,
    is_regex BOOLEAN,
    case_sensitive BOOLEAN,
    match_limit INT
)
RETURNS TABLE (
    chunk_id UUID,
    doc_slug VARCHAR,
    doc_title TEXT,
    path TEXT,
    start_line INT,
    end_line INT,
    verbatim_text TEXT,
    contextualized_text TEXT,
    context_type VARCHAR,
    is_all_refs_resolved BOOLEAN,
    metadata JSONB,
    similarity_score FLOAT,
    full_count BIGINT
) AS $$
DECLARE
    clean_pattern TEXT := trim(query_pattern);
BEGIN
    IF clean_pattern IS NULL OR clean_pattern = '' THEN
        RETURN;
    END IF;
    IF match_limit IS NULL OR match_limit <= 0 THEN
        RAISE EXCEPTION 'match_limit must be a positive integer';
    END IF;

    IF is_regex THEN
        RETURN QUERY
        SELECT 
            c.id AS chunk_id,
            d.doc_slug,
            d.title AS doc_title,
            c.path::text AS path,
            c.start_line,
            c.end_line,
            c.verbatim_text,
            c.contextualized_text,
            c.context_type,
            c.is_all_refs_resolved,
            c.metadata,
            GREATEST(
                word_similarity(clean_pattern, c.verbatim_text),
                word_similarity(clean_pattern, c.contextualized_text)
            )::FLOAT AS similarity_score,
            COUNT(*) OVER()::BIGINT AS full_count
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE (
            (case_sensitive AND (c.verbatim_text ~ clean_pattern OR c.contextualized_text ~ clean_pattern))
            OR (NOT case_sensitive AND (c.verbatim_text ~* clean_pattern OR c.contextualized_text ~* clean_pattern))
        )
        AND (
            target_documents IS NULL 
            OR cardinality(target_documents) = 0 
            OR d.doc_slug = ANY(target_documents)
        )
        AND (path_prefix IS NULL OR c.path <@ path_prefix)
        AND (only_resolved IS NULL OR NOT only_resolved OR c.is_all_refs_resolved = TRUE)
        ORDER BY similarity_score DESC
        LIMIT match_limit;
    ELSE
        RETURN QUERY
        SELECT 
            c.id AS chunk_id,
            d.doc_slug,
            d.title AS doc_title,
            c.path::text AS path,
            c.start_line,
            c.end_line,
            c.verbatim_text,
            c.contextualized_text,
            c.context_type,
            c.is_all_refs_resolved,
            c.metadata,
            GREATEST(
                word_similarity(clean_pattern, c.verbatim_text),
                word_similarity(clean_pattern, c.contextualized_text)
            )::FLOAT AS similarity_score,
            COUNT(*) OVER()::BIGINT AS full_count
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE (
            (case_sensitive AND (c.verbatim_text LIKE '%' || clean_pattern || '%' OR c.contextualized_text LIKE '%' || clean_pattern || '%'))
            OR (NOT case_sensitive AND (
                c.verbatim_text ILIKE '%' || clean_pattern || '%' 
                OR c.contextualized_text ILIKE '%' || clean_pattern || '%'
                OR c.verbatim_text % clean_pattern
                OR c.contextualized_text % clean_pattern
            ))
        )
        AND (
            target_documents IS NULL 
            OR cardinality(target_documents) = 0 
            OR d.doc_slug = ANY(target_documents)
        )
        AND (path_prefix IS NULL OR c.path <@ path_prefix)
        AND (only_resolved IS NULL OR NOT only_resolved OR c.is_all_refs_resolved = TRUE)
        ORDER BY similarity_score DESC
        LIMIT match_limit;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

-- 3. Stored Procedure: Exact & Trigram Grep Count (Strict Contract)
-- Tối ưu hóa: Đồng bộ các bộ lọc phân cấp cây (path_prefix) và ngữ cảnh (only_resolved) với hàm search.
CREATE OR REPLACE FUNCTION verbatim_grep_count(
    query_pattern TEXT,
    target_documents TEXT[],
    path_prefix LTREE,
    only_resolved BOOLEAN,
    is_regex BOOLEAN,
    case_sensitive BOOLEAN
)
RETURNS BIGINT AS $$
DECLARE
    clean_pattern TEXT := trim(query_pattern);
    total BIGINT;
BEGIN
    IF clean_pattern IS NULL OR clean_pattern = '' THEN
        RETURN 0;
    END IF;

    SELECT COUNT(*) INTO total
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE (
        (is_regex AND (
            (case_sensitive AND (c.verbatim_text ~ clean_pattern OR c.contextualized_text ~ clean_pattern))
            OR (NOT case_sensitive AND (c.verbatim_text ~* clean_pattern OR c.contextualized_text ~* clean_pattern))
        ))
        OR (NOT is_regex AND (
            (case_sensitive AND (c.verbatim_text LIKE '%' || clean_pattern || '%' OR c.contextualized_text LIKE '%' || clean_pattern || '%'))
            OR (NOT case_sensitive AND (
                c.verbatim_text ILIKE '%' || clean_pattern || '%' 
                OR c.contextualized_text ILIKE '%' || clean_pattern || '%'
                OR c.verbatim_text % clean_pattern
                OR c.contextualized_text % clean_pattern
            ))
        ))
    )
    AND (
        target_documents IS NULL 
        OR cardinality(target_documents) = 0 
        OR d.doc_slug = ANY(target_documents)
    )
    AND (path_prefix IS NULL OR c.path <@ path_prefix)
    AND (only_resolved IS NULL OR NOT only_resolved OR c.is_all_refs_resolved = TRUE);

    RETURN COALESCE(total, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- 4. Stored Procedure: Generalized Hybrid Search (Strict Contract)
-- Tối ưu hóa:
-- - Bổ sung start_line, end_line.
-- - Bổ sung lọc phân cấp cây tài liệu (path_prefix LTREE) qua index GiST ở cả 2 nhánh dense và sparse.
-- - Bổ sung lọc trạng thái hoàn thiện tham chiếu (only_resolved BOOLEAN).
-- - Fail-fast kiểm tra giá trị tham số hợp lệ (match_limit, rrf_k, ts_config).
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_vector VECTOR(512),
    match_limit INT,
    rrf_k INT,
    target_documents TEXT[],
    path_prefix LTREE,
    only_resolved BOOLEAN,
    ts_config TEXT
)
RETURNS TABLE (
    chunk_id UUID,
    doc_slug VARCHAR,
    doc_title TEXT,
    path TEXT,
    start_line INT,
    end_line INT,
    verbatim_text TEXT,
    contextualized_text TEXT,
    context_type VARCHAR,
    is_all_refs_resolved BOOLEAN,
    metadata JSONB,
    rrf_score DOUBLE PRECISION,
    dense_rank BIGINT,
    sparse_rank BIGINT,
    dense_similarity DOUBLE PRECISION
) AS $$
DECLARE
    clean_query TEXT := trim(COALESCE(query_text, ''));
    resolved_config regconfig;
    ts_query TSQUERY;
    lexemes TEXT[];
    ts_any TSQUERY;
    candidate_limit INT;
    scope_ids UUID[];
BEGIN
    IF match_limit IS NULL OR match_limit <= 0 THEN
        RAISE EXCEPTION 'match_limit must be a positive integer';
    END IF;
    IF rrf_k IS NULL OR rrf_k <= 0 THEN
        RAISE EXCEPTION 'rrf_k must be a positive integer';
    END IF;
    IF ts_config IS NULL OR trim(ts_config) = '' THEN
        RAISE EXCEPTION 'ts_config cannot be null or empty';
    END IF;

    resolved_config := ts_config::regconfig;
    ts_query := CASE WHEN clean_query != '' THEN plainto_tsquery(resolved_config, clean_query) ELSE NULL END;
    candidate_limit := GREATEST(match_limit * 6, 120);

    IF target_documents IS NOT NULL AND cardinality(target_documents) > 0 THEN
        SELECT array_agg(id) INTO scope_ids
        FROM documents WHERE documents.doc_slug = ANY(target_documents);
        IF scope_ids IS NULL THEN
            RETURN;
        END IF;
    END IF;

    IF clean_query != '' AND ts_query IS NOT NULL AND ts_query::text != '' THEN
        BEGIN
            lexemes := string_to_array(replace(ts_query::text, '''', ''), ' & ');
            IF lexemes IS NOT NULL AND array_length(lexemes, 1) >= 2 THEN
                SELECT string_agg(format('''%s'' <-> ''%s''', replace(lexemes[i], '''', ''''''), replace(lexemes[i + 1], '''', '''''')), ' | ')::tsquery
                INTO ts_any
                FROM generate_subscripts(lexemes, 1) AS i
                WHERE i < array_length(lexemes, 1);
            ELSIF lexemes IS NOT NULL AND array_length(lexemes, 1) = 1 THEN
                ts_any := format('''%s''', replace(lexemes[1], '''', ''''''))::tsquery;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            ts_any := NULL;
        END;
    END IF;

    RETURN QUERY
    WITH dense_search AS (
        SELECT
            c.id,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_vector) AS rank_dense,
            (1.0 - (c.embedding <=> query_vector))::DOUBLE PRECISION AS similarity
        FROM chunks c
        WHERE query_vector IS NOT NULL
          AND c.embedding IS NOT NULL
          AND (scope_ids IS NULL OR c.document_id = ANY(scope_ids))
          AND (path_prefix IS NULL OR c.path <@ path_prefix)
          AND (only_resolved IS NULL OR NOT only_resolved OR c.is_all_refs_resolved = TRUE)
        ORDER BY (c.embedding <=> query_vector) ASC
        LIMIT candidate_limit
    ),
    sparse_pool AS (
        SELECT
            c.id,
            c.tsv_content,
            COALESCE(ts_rank(c.tsv_content, ts_any, 32), 0.0) AS base_score
        FROM chunks c
        WHERE (
                (ts_any IS NOT NULL AND c.tsv_content @@ ts_any)
                OR (ts_query IS NOT NULL AND c.tsv_content @@ ts_query)
              )
          AND (scope_ids IS NULL OR c.document_id = ANY(scope_ids))
          AND (path_prefix IS NULL OR c.path <@ path_prefix)
          AND (only_resolved IS NULL OR NOT only_resolved OR c.is_all_refs_resolved = TRUE)
        ORDER BY base_score DESC
        LIMIT candidate_limit * 2
    ),
    sparse_search AS (
        SELECT
            p.id,
            ROW_NUMBER() OVER (
                ORDER BY (
                    p.base_score * 4.0
                    + CASE WHEN ts_query IS NOT NULL AND p.tsv_content @@ ts_query THEN 2.0 ELSE 0.0 END
                ) DESC
            ) AS rank_sparse
        FROM sparse_pool p
        LIMIT candidate_limit
    )
    SELECT
        c.id AS chunk_id,
        d.doc_slug,
        d.title AS doc_title,
        c.path::text AS path,
        c.start_line,
        c.end_line,
        c.verbatim_text,
        c.contextualized_text,
        c.context_type,
        c.is_all_refs_resolved,
        c.metadata,
        (COALESCE(1.0 / (rrf_k + d_s.rank_dense), 0.0) +
         COALESCE(1.0 / (rrf_k + s.rank_sparse), 0.0))::DOUBLE PRECISION AS rrf_score,
        COALESCE(d_s.rank_dense, 999)::BIGINT AS dense_rank,
        COALESCE(s.rank_sparse, 999)::BIGINT AS sparse_rank,
        COALESCE(d_s.similarity, 0.0)::DOUBLE PRECISION AS dense_similarity
    FROM dense_search d_s
    FULL OUTER JOIN sparse_search s ON d_s.id = s.id
    JOIN chunks c ON c.id = COALESCE(d_s.id, s.id)
    JOIN documents d ON c.document_id = d.id
    ORDER BY rrf_score DESC
    LIMIT match_limit;
END;
$$ LANGUAGE plpgsql STABLE;
