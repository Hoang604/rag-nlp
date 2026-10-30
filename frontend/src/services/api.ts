import {
  AnswerPayload,
  AnswerResponse,
  CorpusDocument,
  CurateEdgesPayload,
  CurateEdgesResult,
  EvalCase,
  EvalCaseUpdatePayload,
  GraphTraversalStep,
  GraphTraversePayload,
  GraphVisualizerResponse,
  HealthResponse,
  ProviderStatus,
  RawTextResponse,
  RelationTypeCatalogItem,
  SearchPayload,
  SearchResponse,
} from '../types/api';
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

  // 2. Production Documents Catalog
  async getDocuments(): Promise<CorpusDocument[]> {
    return this.request<CorpusDocument[]>('/documents');
  }

  // 3. Document Hierarchy Tree
  async getDocumentTree(docSlug: string): Promise<DocumentTreeResponse> {
    return this.request<DocumentTreeResponse>(
      `/documents/${encodeURIComponent(docSlug)}/tree`
    );
  }

  // 4. Raw Document Text
  async getDocumentRaw(docSlug: string): Promise<RawTextResponse> {
    return this.request<RawTextResponse>(
      `/documents/${encodeURIComponent(docSlug)}/raw`
    );
  }

  // 5. Relational Knowledge Graph
  async getDocumentGraph(docSlug: string): Promise<GraphVisualizerResponse> {
    return this.request<GraphVisualizerResponse>(
      `/documents/${encodeURIComponent(docSlug)}/graph`
    );
  }

  // 6. Runtime Graph Enrichment
  async curateEdges(payload: CurateEdgesPayload): Promise<CurateEdgesResult> {
    return this.request<CurateEdgesResult>('/documents/curate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // 7. Search & Retrieval
  async search(payload: SearchPayload): Promise<SearchResponse> {
    return this.request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({ limit: 5, ...payload }),
    });
  }

  // 8. Relations Catalog
  async getRelations(): Promise<RelationTypeCatalogItem[]> {
    return this.request<RelationTypeCatalogItem[]>('/relations');
  }

  // 9. Graph Traversal
  async traverseGraph(
    docSlug: string,
    payload: GraphTraversePayload
  ): Promise<GraphTraversalStep[]> {
    return this.request<GraphTraversalStep[]>(
      `/documents/${encodeURIComponent(docSlug)}/graph/traverse`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  // 10. Grounded Q&A Providers & Execution
  async getAnswerProviders(): Promise<ProviderStatus[]> {
    return this.request<ProviderStatus[]>('/answer/providers');
  }

  async askQuestion(payload: AnswerPayload): Promise<AnswerResponse> {
    return this.request<AnswerResponse>('/answer', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // 11. Evaluation Suite Endpoints
  async getEvalCases(): Promise<EvalCase[]> {
    return this.request<EvalCase[]>('/eval/cases');
  }

  async updateEvalCase(
    caseId: string,
    payload: EvalCaseUpdatePayload
  ): Promise<EvalCase> {
    return this.request<EvalCase>(`/eval/cases/${encodeURIComponent(caseId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteEvalCase(caseId: string): Promise<{ status: string; id: string }> {
    return this.request<{ status: string; id: string }>(
      `/eval/cases/${encodeURIComponent(caseId)}`,
      {
        method: 'DELETE',
      }
    );
  }

  async runEvalCase(caseId: string): Promise<EvalCase> {
    return this.request<EvalCase>(
      `/eval/cases/${encodeURIComponent(caseId)}/run`,
      {
        method: 'POST',
      }
    );
  }

  async runAllEvalCases(): Promise<EvalCase[]> {
    return this.request<EvalCase[]>('/eval/run', {
      method: 'POST',
    });
  }
}

export const api = new ApiClient();
