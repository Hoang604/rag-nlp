import {
  BatchPatchPayload,
  BatchPatchResponse,
  CreateEdgePayload,
  CreateSessionPayload,
  DeleteEdgePayload,
  FinalizeChunksResponse,
  UnfinalizeChunksResponse,
  GenericSuccessResponse,
  HealthResponse,
  PromoteSessionPayload,
  PromotionResultResponse,
  RawTextResponse,
  CorpusDocument,
  ReparentSubtreePayload,
  ReparentSubtreeResponse,
  ReplayVerificationResponse,
  SearchPayload,
  SearchResponse,
  StatusTransitionPayload,
  WALRecord,
  RelationTypeCatalogItem,
  GraphTraversePayload,
  GraphTraversalStep,
  CorpusGrepPayload,
  CorpusGrepResponse,
} from '../types/api';
import { SessionDiffResponse } from '../types/diff';
import { PreFlightValidationResponse } from '../types/preflight';
import {
  StagingDocumentSession,
  StagingEdge,
  StagingSessionSummary,
  StagingStatus,
} from '../types/staging';
import { DocumentTreeResponse } from '../types/tree';

const API_BASE = '/api';

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMessage = `API Error ${response.status}: ${response.statusText}`;
      try {
        const errorJson = (await response.json()) as {
          error?: { message?: string; code?: number };
          detail?: string | { message?: string };
        };
        if (errorJson.error?.message) {
          errorMessage = errorJson.error.message;
        } else if (typeof errorJson.detail === 'string') {
          errorMessage = errorJson.detail;
        } else if (
          typeof errorJson.detail === 'object' &&
          errorJson.detail?.message
        ) {
          errorMessage = errorJson.detail.message;
        }
      } catch {
        // Fallback to response.statusText
      }
      throw new Error(errorMessage);
    }

    return response.json() as Promise<T>;
  }

  // 1. Health Probe
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // 2. Session Listing & Creation
  async listSessions(): Promise<StagingSessionSummary[]> {
    return this.request<StagingSessionSummary[]>('/staging');
  }

  async getSession(docSlug: string): Promise<StagingDocumentSession> {
    return this.request<StagingDocumentSession>(
      `/staging/${encodeURIComponent(docSlug)}`
    );
  }

  async createSessionRaw(
    payload: CreateSessionPayload
  ): Promise<StagingDocumentSession> {
    return this.request<StagingDocumentSession>('/staging/raw', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async uploadDocumentFile(
    formData: FormData
  ): Promise<StagingDocumentSession> {
    const url = `${API_BASE}/staging/upload`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      let errorMessage = `API Error ${response.status}: ${response.statusText}`;
      try {
        const errorJson = (await response.json()) as {
          error?: { message?: string; code?: number };
          detail?: string | { message?: string };
        };
        if (errorJson.error?.message) {
          errorMessage = errorJson.error.message;
        } else if (typeof errorJson.detail === 'string') {
          errorMessage = errorJson.detail;
        } else if (
          typeof errorJson.detail === 'object' &&
          errorJson.detail?.message
        ) {
          errorMessage = errorJson.detail.message;
        }
      } catch {
        // Fallback to response.statusText
      }
      throw new Error(errorMessage);
    }

    return response.json() as Promise<StagingDocumentSession>;
  }

  async deleteSession(docSlug: string): Promise<GenericSuccessResponse> {
    return this.request<GenericSuccessResponse>(
      `/staging/${encodeURIComponent(docSlug)}`,
      {
        method: 'DELETE',
      }
    );
  }

  // 3. Document Hierarchy Tree
  async getDocumentTree(docSlug: string): Promise<DocumentTreeResponse> {
    return this.request<DocumentTreeResponse>(
      `/staging/${encodeURIComponent(docSlug)}/tree`
    );
  }

  // 4. Surgical Chunk Patching
  async patchChunks(
    docSlug: string,
    payload: BatchPatchPayload
  ): Promise<BatchPatchResponse> {
    return this.request<BatchPatchResponse>(
      `/staging/${encodeURIComponent(docSlug)}/patch`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async finalizeChunks(
    docSlug: string,
    paths: string[]
  ): Promise<FinalizeChunksResponse> {
    return this.request<FinalizeChunksResponse>(
      `/staging/${encodeURIComponent(docSlug)}/finalize`,
      {
        method: 'POST',
        body: JSON.stringify({ paths }),
      }
    );
  }

  async unfinalizeChunks(
    docSlug: string,
    paths: string[]
  ): Promise<UnfinalizeChunksResponse> {
    return this.request<UnfinalizeChunksResponse>(
      `/staging/${encodeURIComponent(docSlug)}/unfinalize`,
      {
        method: 'POST',
        body: JSON.stringify({ paths }),
      }
    );
  }

  // 5. Relational Graph Edges
  async listEdges(docSlug: string): Promise<StagingEdge[]> {
    return this.request<StagingEdge[]>(
      `/staging/${encodeURIComponent(docSlug)}/edges`
    );
  }

  async addEdges(
    docSlug: string,
    edges: CreateEdgePayload[]
  ): Promise<StagingDocumentSession> {
    return this.request<StagingDocumentSession>(
      `/staging/${encodeURIComponent(docSlug)}/edges`,
      {
        method: 'POST',
        body: JSON.stringify(edges),
      }
    );
  }

  async deleteEdge(
    docSlug: string,
    payload: DeleteEdgePayload
  ): Promise<GenericSuccessResponse> {
    const query = new URLSearchParams({
      source_path: payload.source_path,
    });
    if (payload.relation_type) query.set('relation_type', payload.relation_type);
    if (payload.target_path) query.set('target_path', payload.target_path);
    if (payload.clear_all_targets) query.set('clear_all_targets', 'true');

    return this.request<GenericSuccessResponse>(
      `/staging/${encodeURIComponent(docSlug)}/edges?${query.toString()}`,
      {
        method: 'DELETE',
      }
    );
  }

  // 6. Status Transition & Version Diff
  async updateSessionStatus(
    docSlug: string,
    status: StagingStatus,
    actor = 'HUMAN:reviewer',
    description = ''
  ): Promise<StagingDocumentSession> {
    const payload: StatusTransitionPayload = {
      status,
      actor,
      description,
    };
    return this.request<StagingDocumentSession>(
      `/staging/${encodeURIComponent(docSlug)}/status`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async getSessionDiff(docSlug: string): Promise<SessionDiffResponse> {
    return this.request<SessionDiffResponse>(
      `/staging/${encodeURIComponent(docSlug)}/diff`
    );
  }

  async getRawText(docSlug: string): Promise<RawTextResponse> {
    return this.request<RawTextResponse>(
      `/staging/${encodeURIComponent(docSlug)}/raw`
    );
  }

  // 7. Pre-Flight Validation & Human Promotion
  async validateSession(docSlug: string): Promise<PreFlightValidationResponse> {
    return this.request<PreFlightValidationResponse>(
      `/staging/${encodeURIComponent(docSlug)}/validate`
    );
  }

  async promoteSession(
    docSlug: string,
    payload: PromoteSessionPayload = { compute_embeddings: true }
  ): Promise<PromotionResultResponse> {
    return this.request<PromotionResultResponse>(
      `/staging/${encodeURIComponent(docSlug)}/promote`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async reopenSession(
    docSlug: string,
    reason = 'User reopened session for amendment'
  ): Promise<StagingDocumentSession> {
    return this.request<StagingDocumentSession>(
      `/staging/${encodeURIComponent(docSlug)}/reopen`,
      {
        method: 'POST',
        body: JSON.stringify({ actor: 'HUMAN:reviewer', reason }),
      }
    );
  }

  // 7b. Subtree Reparenting
  async reparentSubtree(
    docSlug: string,
    payload: ReparentSubtreePayload
  ): Promise<ReparentSubtreeResponse> {
    return this.request<ReparentSubtreeResponse>(
      `/staging/${encodeURIComponent(docSlug)}/reparent`,
      {
        method: 'POST',
        body: JSON.stringify({
          dry_run: false,
          actor: 'HUMAN:reviewer',
          ...payload,
        }),
      }
    );
  }

  // 7c. Write-Ahead Log Journal & Replay
  async getWalJournal(docSlug: string): Promise<WALRecord[]> {
    return this.request<WALRecord[]>(
      `/staging/${encodeURIComponent(docSlug)}/wal`
    );
  }

  async replaySession(
    docSlug: string,
    upToLsn?: number
  ): Promise<ReplayVerificationResponse> {
    const query = upToLsn !== undefined ? `?up_to_lsn=${upToLsn}` : '';
    return this.request<ReplayVerificationResponse>(
      `/staging/${encodeURIComponent(docSlug)}/replay${query}`,
      {
        method: 'POST',
      }
    );
  }

  // 8. Retrieval against the promoted corpus
  async search(payload: SearchPayload): Promise<SearchResponse> {
    return this.request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({ limit: 5, ...payload }),
    });
  }

  // 9. The promoted corpus, for the retrieval scope selector
  async documents(): Promise<CorpusDocument[]> {
    return this.request<CorpusDocument[]>('/documents');
  }

  // 10. In-Memory Grep
  async grepSession(
    docSlug: string,
    payload: {
      pattern: string;
      is_regex?: boolean;
      case_sensitive?: boolean;
      search_in?: string;
      limit?: number;
    }
  ): Promise<{
    doc_slug: string;
    pattern: string;
    total_hits: number;
    hits: Array<{
      path: string;
      field_matched: string;
      match_snippet: string;
      verbatim_text: string;
      contextualized_text: string;
      char_length: number;
      metadata?: Record<string, unknown>;
    }>;
  }> {
    return this.request(
      `/staging/${encodeURIComponent(docSlug)}/grep`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  // 11. Cross-Document Unresolved References Backlog
  async getUnresolvedBacklog(
    docSlug: string,
    limit = 50
  ): Promise<{
    doc_slug: string | null;
    total_unresolved: number;
    items: Array<{
      chunk_id: string;
      source_path: string;
      doc_slug: string;
      doc_title: string;
      target_path: string;
      context_type: string;
    }>;
  }> {
    return this.request(
      `/staging/${encodeURIComponent(docSlug)}/backlog?limit=${limit}`
    );
  }

  // 12. Relation Types Catalog
  async getRelations(): Promise<RelationTypeCatalogItem[]> {
    return this.request<RelationTypeCatalogItem[]>('/relations');
  }

  // 13. Knowledge Graph Traversal
  async traverseGraph(
    docSlug: string,
    payload: GraphTraversePayload
  ): Promise<GraphTraversalStep[]> {
    return this.request<GraphTraversalStep[]>(
      `/staging/${encodeURIComponent(docSlug)}/graph/traverse`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  // 14. Corpus-wide Exact / Trigram Verbatim Grep
  async grepCorpus(payload: CorpusGrepPayload): Promise<CorpusGrepResponse> {
    return this.request<CorpusGrepResponse>('/corpus/grep', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();

