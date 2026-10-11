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
  citation_text: string;
  rationale?: string | null;
}

export interface LinkChunksResponse {
  status: string;
  source_path: string;
  target_path: string;
  relation_type: string;
  citation_text: string;
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
  pattern: string;
  limit?: number;
  rerank?: boolean | null;
  doc_slugs?: string[];
  path_prefix?: string;
  is_regex?: boolean;
  case_sensitive?: boolean;
  order_by_reading_order?: boolean;
}

export interface AgentVennHit {
  path: string;
  start_line: number;
  end_line: number;
  context: string;
  text: string;
  metadata?: Record<string, unknown>;
  semantic_rank?: number | null;
  verbatim_rank?: number | null;
  semantic_score?: number | null;
  verbatim_score?: number | null;
  rerank_score?: number | null;
}

export interface SearchResponse {
  query: string;
  pattern: string;
  elapsed_ms: number;
  confidence: 'high' | 'medium' | 'low' | 'none' | string;
  total_unique_hits: number;
  both_hits: AgentVennHit[];
  semantic_only_hits: AgentVennHit[];
  verbatim_only_hits: AgentVennHit[];
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


