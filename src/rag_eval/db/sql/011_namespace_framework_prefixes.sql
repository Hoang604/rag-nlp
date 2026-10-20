-- 011_namespace_framework_prefixes.sql: In-place namespace prefixing for Next.js documents and chunks

-- 1. Prefix existing Next.js documents with 'nextjs.' when not already prefixed
UPDATE documents
SET doc_slug = 'nextjs.' || doc_slug,
    metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{framework}', '"nextjs"'::jsonb, true),
    updated_at = CURRENT_TIMESTAMP
WHERE (metadata->>'format_type' = 'nextjs_mdx' OR metadata->>'framework' = 'nextjs')
  AND doc_slug NOT LIKE 'nextjs.%'
  AND doc_slug != 'nextjs';

-- 2. Prefix chunks belonging to Next.js documents with 'nextjs.' when not already prefixed
-- Note:trg_chunks_tsv_update only fires on UPDATE OF contextualized_text, so updating path & metadata is instantaneous
UPDATE chunks c
SET path = ('nextjs.' || c.path::text)::ltree,
    metadata = jsonb_set(COALESCE(c.metadata, '{}'::jsonb), '{framework}', '"nextjs"'::jsonb, true),
    updated_at = CURRENT_TIMESTAMP
FROM documents d
WHERE c.document_id = d.id
  AND d.doc_slug LIKE 'nextjs.%'
  AND c.path::text NOT LIKE 'nextjs.%';
