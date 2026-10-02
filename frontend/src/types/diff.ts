import { StagingChunk } from './staging';

export interface AuditDiffEntry {
  path: string;
  change_type: 'ADDED' | 'MODIFIED' | 'DELETED';
  field_name?: string | null;
  old_value?: unknown;
  new_value?: unknown;
  description: string;
}

export interface ModifiedChunkDiff {
  path: string;
  current_chunk: StagingChunk;
  baseline_chunk?: Record<string, unknown>;
  field_diffs: Record<string, { old: unknown; new: unknown }>;
}

export interface SessionDiffResponse {
  doc_slug: string;
  total_changes: number;
  added_chunks: StagingChunk[];
  modified_chunks: ModifiedChunkDiff[] | Record<string, unknown>[];
  deleted_chunks: Record<string, unknown>[];
  edge_diffs: Record<string, unknown>[];
  diff_entries: AuditDiffEntry[];
}
