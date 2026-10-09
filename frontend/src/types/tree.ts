export type NodeType = 'DOCUMENT' | 'SECTION' | 'PARAGRAPH' | 'TABLE' | 'LIST' | 'CODE' | string;

export interface DocumentTreeNode {
  path: string;
  label: string;
  node_type: NodeType | string;
  verbatim_text: string;
  contextualized_text: string;
  start_line: number;
  end_line: number;
  metadata: Record<string, unknown>;
  children: DocumentTreeNode[];
}

export interface DocumentTreeResponse {
  doc_slug: string;
  title: string;
  total_nodes: number;
  total_chunks: number;
  root: DocumentTreeNode;
}
