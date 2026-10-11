-- 008_verbatim_grep_reading_order.sql: Add document reading order sorting support to verbatim_grep

DROP FUNCTION IF EXISTS verbatim_grep(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN, INT) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN, INT, BOOLEAN) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep CASCADE;

CREATE OR REPLACE FUNCTION verbatim_grep(
    query_pattern TEXT,
    target_documents TEXT[],
    path_prefix LTREE,
    is_regex BOOLEAN,
    case_sensitive BOOLEAN,
    match_limit INT,
    order_by_reading_order BOOLEAN DEFAULT FALSE
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
        ORDER BY 
            CASE WHEN order_by_reading_order THEN d.doc_slug ELSE NULL END ASC,
            CASE WHEN order_by_reading_order THEN c.start_line ELSE NULL END ASC,
            CASE WHEN order_by_reading_order THEN c.path::text ELSE NULL END ASC,
            CASE WHEN NOT order_by_reading_order THEN similarity_score ELSE NULL END DESC
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
        ORDER BY 
            CASE WHEN order_by_reading_order THEN d.doc_slug ELSE NULL END ASC,
            CASE WHEN order_by_reading_order THEN c.start_line ELSE NULL END ASC,
            CASE WHEN order_by_reading_order THEN c.path::text ELSE NULL END ASC,
            CASE WHEN NOT order_by_reading_order THEN similarity_score ELSE NULL END DESC
        LIMIT match_limit;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;
