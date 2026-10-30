export interface HealthResponse {
  status: string;
  database: string;
  timestamp: string;
}

export interface CorpusDocument {
  doc_slug: string;
  title: string;
  chunk_count: number;
}

export interface RawTextResponse {
  doc_slug: string;
  title: string;
  raw_text: string;
  chunks_count: number;
}

export interface GraphVisualizerNode {
  path: string;
  label: string;
  node_type: string;
  in_degree: number;
  out_degree: number;
}

export interface GraphVisualizerEdge {
  source_path: string;
  target_path: string;
  relation_type: string;
  rationale?: string | null;
}

export interface GraphVisualizerResponse {
  doc_slug: string;
  nodes: GraphVisualizerNode[];
  edges: GraphVisualizerEdge[];
}

export interface EdgeKey {
  source_path: string;
  target_path: string;
  relation_type: string;
}

export interface EdgeProposal extends EdgeKey {
  citation_text: string;
  rationale?: string | null;
}

export interface CurateEdgesPayload {
  add_edges?: EdgeProposal[] | null;
  remove_edges?: EdgeKey[] | null;
  reason: string;
}

export interface CurateEdgesResult {
  added: EdgeKey[];
  existing: EdgeKey[];
  removed: EdgeKey[];
  not_found: EdgeKey[];
  message: string;
}

export interface SearchPayload {
  query: string;
  pattern: string;
  limit?: number;
  rerank?: boolean | null;
  doc_slugs?: string[];
  path_prefix?: string;
  is_regex?: boolean;
  case_sensitive?: boolean;
  order_by_reading_order?: boolean;
}

export interface SearchDocument {
  title: string;
  doc_slug: string;
  metadata?: Record<string, unknown>;
}

export interface SearchProvision {
  path: string;
  text: string;
  start_line: number;
  end_line: number;
  metadata?: Record<string, unknown>;
  found_in: 'both' | 'semantic_only' | 'verbatim_only';
  rank: number;
}

export interface ProvisionGroup<P = SearchProvision> {
  doc_slug: string;
  context: string;
  provisions: P[];
}

export interface SearchResponse {
  query: string;
  pattern: string;
  elapsed_ms: number;
  confidence: 'high' | 'medium' | 'low' | 'none' | string;
  documents: Record<string, SearchDocument>;
  groups: ProvisionGroup[];
  verbatim_total: number;
  verbatim_truncated: boolean;
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
  limit?: number;
  filter_relations?: string[];
}

export interface GraphTraversalStep {
  edge_id: string;
  source_chunk_id: string;
  target_chunk_id: string;
  relation_type: string;
  depth: number;
  source_path: string;
  target_path: string;
  target_text: string;
  target_contextualized_text: string;
  target_doc_slug: string;
  target_start_line: number;
  target_end_line: number;
  citation_text: string;
  rationale?: string | null;
}

export type ProviderId = 'agy' | 'claude' | 'codex';

export interface ProviderStatus {
  id: ProviderId;
  label: string;
  available: boolean;
}

export interface AnswerCitation {
  index: number;
  path: string;
  doc_slug: string;
  doc_title: string;
  start_line: number;
  end_line: number;
  verbatim_text: string;
  contextualized_text: string;
  citation_text?: string | null;
}

export interface AnswerPayload {
  question: string;
  provider: ProviderId;
  agent_mode: boolean;
  limit?: number;
  doc_slugs?: string[];
  session_id?: string;
}

export interface AnswerResponse {
  question: string;
  provider: ProviderId;
  answer: string;
  abstained: boolean;
  citations: AnswerCitation[];
  retrieval_ms: number;
  llm_ms: number;
  total_ms: number;
}

export interface QAWebhookEvent {
  event:
    | 'ws_connected'
    | 'qa_started'
    | 'tool_start'
    | 'tool_done'
    | 'tool_error'
    | 'answer_submitted'
    | 'qa_completed'
    | 'qa_error'
    | string;
  session_id?: string | null;
  question?: string;
  timestamp?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  error?: string;
  elapsed_ms?: number;
  payload?: AnswerResponse | Record<string, unknown>;
}

export interface ExpectedTarget {
  doc_slug: string;
  path_suffix: string;
}

export interface EvalHit {
  rank: number;
  path: string;
  doc_slug: string;
  found_in: 'both' | 'semantic_only' | 'verbatim_only' | string;
  start_line: number;
  end_line: number;
  snippet: string;
  matched: boolean;
}

export interface EvalCase {
  id: string;
  test_set: string;
  domain: string;
  question: string;
  query: string;
  pattern: string;
  expected: ExpectedTarget[];
  is_regex: boolean;
  case_sensitive: boolean;
  doc_slugs: string[];
  path_prefix?: string | null;
  note: string;
  rank?: number | null;
  found_in?: string | null;
  matched_path?: string | null;
  elapsed_ms?: number | null;
  top_hits: EvalHit[];
}

export interface EvalCaseUpdatePayload {
  test_set: string;
  domain: string;
  question: string;
  query: string;
  pattern: string;
  expected: ExpectedTarget[];
  is_regex: boolean;
  case_sensitive: boolean;
  doc_slugs: string[];
  path_prefix?: string | null;
  note: string;
}



