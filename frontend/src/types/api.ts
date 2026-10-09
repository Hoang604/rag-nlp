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

export interface LinkChunksPayload {
  source_path: string;
  target_path: string;
  relation_type: string;
  rationale?: string | null;
}

export interface LinkChunksResponse {
  status: string;
  source_path: string;
  target_path: string;
  relation_type: string;
  created: boolean;
  rationale?: string | null;
}

export interface UnlinkChunksPayload {
  source_path: string;
  target_path: string;
  relation_type?: string | null;
}

export interface UnlinkChunksResponse {
  status: string;
  source_path: string;
  target_path: string;
  removed_edges_count: number;
}

export interface SearchPayload {
  query: string;
  limit?: number;
  rerank?: boolean | null;
  doc_slugs?: string[];
  path_prefix?: string;
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
  rationale?: string | null;
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
