import { StagingChunk } from './staging';

export interface CreateSessionPayload {
  doc_slug: string;
  title: string;
  raw_text: string;
  valid_from?: string | null;
  valid_to?: string | null;
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
}

/** One promoted document, for scoping a query. */
export interface CorpusDocument {
  doc_slug: string;
  title: string;
  valid_from: string | null;
  valid_to: string | null;
  in_force: boolean;
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
