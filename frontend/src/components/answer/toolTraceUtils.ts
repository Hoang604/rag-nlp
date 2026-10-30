export interface ToolTraceItem {
  id: string;
  tool: string;
  argsSummary: string;
  args?: Record<string, unknown>;
  result?: unknown;
  status: 'running' | 'done' | 'error';
  elapsedMs?: number;
  error?: string;
  timestamp: string;
}

export interface ParsedProvision {
  path: string;
  text: string;
  start_line: number;
  end_line: number;
  found_in?: string;
  rank?: number;
}

export interface ParsedProvisionGroup {
  doc_slug: string;
  context: string;
  provisions: ParsedProvision[];
}

export interface ParsedGraphLink {
  from_path: string;
  direction: string;
  relation_type: string;
  citation_text: string;
  depth: number;
  total: number;
  groups: ParsedProvisionGroup[];
}

export function isRecord(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

export function summarizeArgs(args?: Record<string, unknown>): string {
  if (!args) return '';
  const parts: string[] = [];
  if (typeof args.query === 'string' && args.query) {
    parts.push(`query="${args.query}"`);
  }
  if (typeof args.pattern === 'string' && args.pattern) {
    parts.push(`pattern="${args.pattern}"`);
  }
  if (typeof args.path === 'string' && args.path) {
    parts.push(`path="${args.path}"`);
  }
  if (typeof args.direction === 'string' && args.direction) {
    parts.push(`dir=${args.direction}`);
  }
  if (typeof args.source_path === 'string' && args.source_path) {
    parts.push(`source="${args.source_path}"`);
  }
  if (typeof args.path_or_slug === 'string' && args.path_or_slug) {
    const lineRange =
      typeof args.start_line === 'number'
        ? ` L${args.start_line}${typeof args.end_line === 'number' ? `–${args.end_line}` : '+'}`
        : '';
    parts.push(`target="${args.path_or_slug}"${lineRange}`);
  }
  if (Array.isArray(args.citations)) {
    parts.push(`citations=${args.citations.length}`);
  }
  if (typeof args.abstained === 'boolean' && args.abstained) {
    parts.push('abstained=true');
  }
  if (parts.length > 0) return parts.join(' · ');
  try {
    return JSON.stringify(args).slice(0, 120);
  } catch {
    return '';
  }
}

export function summarizeResultBadge(tool: string, result: unknown): string | null {
  if (!isRecord(result)) return null;

  if (tool === 'hybrid_search' || tool === 'hierarchical_navigate') {
    const groups = Array.isArray(result.groups) ? result.groups : [];
    let chunkCount = 0;
    const docSet = new Set<string>();
    for (const g of groups) {
      if (isRecord(g)) {
        if (typeof g.doc_slug === 'string') docSet.add(g.doc_slug);
        if (Array.isArray(g.provisions)) chunkCount += g.provisions.length;
      }
    }
    if (tool === 'hybrid_search') {
      return `${chunkCount} chunks · ${docSet.size} tài liệu`;
    }
    return `${chunkCount} nodes`;
  }

  if (tool === 'get_raw') {
    const start = typeof result.start_line === 'number' ? result.start_line : 1;
    const end = typeof result.end_line === 'number' ? result.end_line : start;
    const count = Math.max(0, end - start + 1);
    return `L${start}–${end} (${count} dòng)`;
  }

  if (tool === 'graph_traverse') {
    const links = Array.isArray(result.links) ? result.links.length : 0;
    return `${links} liên kết`;
  }

  if (tool === 'submit_grounded_answer') {
    if (result.abstained === true) return 'Abstained';
    const cites = Array.isArray(result.citations) ? result.citations.length : 0;
    return `${cites} trích dẫn hợp lệ`;
  }

  if (tool === 'graph_curate_edges') {
    const added = Array.isArray(result.added) ? result.added.length : 0;
    const removed = Array.isArray(result.removed) ? result.removed.length : 0;
    return `+${added} / -${removed} cạnh`;
  }

  return null;
}

export function parseProvisionGroups(rawGroups: unknown): ParsedProvisionGroup[] {
  if (!Array.isArray(rawGroups)) return [];
  const groups: ParsedProvisionGroup[] = [];
  for (const g of rawGroups) {
    if (!isRecord(g)) continue;
    const docSlug = typeof g.doc_slug === 'string' ? g.doc_slug : '';
    const context = typeof g.context === 'string' ? g.context : '';
    const rawProvs = Array.isArray(g.provisions) ? g.provisions : [];
    const provisions: ParsedProvision[] = [];
    for (const p of rawProvs) {
      if (!isRecord(p)) continue;
      provisions.push({
        path: typeof p.path === 'string' ? p.path : '',
        text: typeof p.text === 'string' ? p.text : '',
        start_line: typeof p.start_line === 'number' ? p.start_line : 1,
        end_line: typeof p.end_line === 'number' ? p.end_line : 1,
        found_in: typeof p.found_in === 'string' ? p.found_in : undefined,
        rank: typeof p.rank === 'number' ? p.rank : undefined,
      });
    }
    if (provisions.length > 0) {
      groups.push({ doc_slug: docSlug, context, provisions });
    }
  }
  return groups;
}
