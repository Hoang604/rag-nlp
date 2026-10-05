import { StagingChunk } from './staging';

export interface CreateSessionPayload {
  doc_slug: string;
  title: string;
  raw_text: string;
  metadata?: Record<string, unknown>;
}

export interface BatchPatchPayload {
  updated_chunks: StagingChunk[];
  removed_paths: string[];
}

export interface BatchPatchResponse {
  status: string;
  doc_slug: string;
  updated_count: number;
  removed_count: number;
  total_chunks: number;
}

export interface FinalizeChunksPayload {
  paths: string[];
}

export interface FinalizeChunksResponse {
  status: string;
  doc_slug: string;
  finalized_count: number;
  pending_remaining: number;
}

export interface UnfinalizeChunksPayload {
  paths: string[];
}

export interface UnfinalizeChunksResponse {
  status: string;
  doc_slug: string;
  unfinalized_count: number;
  pending_remaining: number;
}

export interface CreateEdgePayload {
  source_path: string;
  target_path: string;
  relation_type: string;
}

export interface DeleteEdgePayload {
  source_path: string;
  target_path?: string | null;
  relation_type?: string | null;
  clear_all_targets?: boolean;
}

export interface StatusTransitionPayload {
  status: string;
  actor?: string;
  description?: string;
}

export interface PromoteSessionPayload {
  reviewer_notes?: string | null;
  compute_embeddings?: boolean;
}

export interface PromotionResultResponse {
  status: 'SUCCESS' | 'FAILED';
  doc_slug: string;
  document_id: string;
  chunks_promoted: number;
  edges_promoted: number;
  promoted_at: string;
  message: string;
}

export interface RawTextResponse {
  doc_slug: string;
  title: string;
  raw_text: string;
  chunks_count: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  timestamp: string;
}

export interface GenericSuccessResponse {
  status: string;
  message: string;
  doc_slug?: string | null;
}

export interface ApiErrorResponse {
  error: {
    code: number;
    message: string;
    data?: unknown;
  };
}

export interface SearchPayload {
  /** null follows the server default; true or false overrides it. */
  rerank?: boolean | null;
  query: string;
  limit?: number;
  /** Empty means the whole corpus. Naming a document not in it returns nothing. */
  doc_slugs?: string[];
  path_prefix?: string;
  only_resolved?: boolean;
}

/** One promoted document, for scoping a query. */
export interface CorpusDocument {
  doc_slug: string;
  title: string;
  chunk_count: number;
}

export interface SearchHit {
  rank: number;
  doc_slug: string;
  doc_title: string;
  path: string;
  verbatim_text: string;
  contextualized_text: string;
  score: number;
  dense_similarity: number;
  keyword_matched: boolean;
  rerank_score: number | null;
  is_table: boolean;
  table_summary: string | null;
}

export interface SearchResponse {
  query: string;
  elapsed_ms: number;
  confidence: 'high' | 'medium' | 'low' | 'none' | string;
  hits: SearchHit[];
}

export interface ReparentSubtreePayload {
  old_path_prefix: string;
  new_path_prefix: string;
  dry_run?: boolean;
  actor?: string;
}

export interface ReparentSubtreeResponse {
  status: string;
  doc_slug: string;
  dry_run: boolean;
  affected_chunks_count: number;
  affected_edges_count: number;
  old_path_prefix: string;
  new_path_prefix: string;
  total_chunks: number;
}

export interface WALRecord {
  lsn: number;
  timestamp: string;
  actor: string;
  op_type: string;
  description: string;
  payload: Record<string, unknown>;
  checksum: string;
}

export interface ReplayVerificationResponse {
  status: string;
  doc_slug: string;
  applied_lsn: number;
  is_deterministic: boolean;
  total_chunks: number;
  total_edges: number;
  message: string;
}

export interface StagingGrepPayload {
  pattern: string;
  is_regex?: boolean;
  case_sensitive?: boolean;
  search_in?: 'ALL' | 'VERBATIM' | 'CONTEXT' | 'PATH' | 'METADATA' | string;
  limit?: number;
}

export interface StagingGrepHit {
  path: string;
  field_matched: string;
  match_snippet: string;
  verbatim_text: string;
  contextualized_text: string;
  char_length: number;
  metadata?: Record<string, unknown>;
}

export interface StagingGrepResponse {
  doc_slug: string;
  pattern: string;
  total_hits: number;
  hits: StagingGrepHit[];
}

export interface UnresolvedBacklogItem {
  chunk_id: string;
  source_path: string;
  doc_slug: string;
  doc_title: string;
  target_path: string;
  context_type: string;
}

export interface UnresolvedBacklogResponse {
  doc_slug: string | null;
  total_unresolved: number;
  items: UnresolvedBacklogItem[];
}

export interface RelationTypeCatalogItem {
  code: string;
  description: string;
  is_symmetric: boolean;
}

export interface GraphTraversePayload {
  source_path: string;
  nav_direction?: 'OUTGOING' | 'INCOMING' | 'BOTH';
  depth_limit?: number;
  filter_relations?: string[];
}

export interface GraphTraversalStep {
  edge_id: string;
  source_chunk_id: string;
  target_chunk_id: string;
  relation_type: string;
  depth: number;
  target_path: string;
  target_text: string;
}

export interface CorpusGrepPayload {
  pattern: string;
  is_regex?: boolean;
  case_sensitive?: boolean;
  limit?: number;
}

export interface CorpusGrepHit {
  chunk_id: string;
  doc_slug: string;
  path: string;
  start_line: number;
  end_line: number;
  char_offset: number;
  match_snippet: string;
  verbatim_text: string;
  metadata?: Record<string, unknown>;
}

export interface CorpusGrepResponse {
  pattern: string;
  is_regex: boolean;
  total_matches: number;
  returned: number;
  truncated: boolean;
  matches: CorpusGrepHit[];
}

