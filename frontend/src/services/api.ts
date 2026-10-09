import {
  CorpusDocument,
  CorpusGrepPayload,
  CorpusGrepResponse,
  GraphTraversePayload,
  GraphTraversalStep,
  GraphVisualizerResponse,
  HealthResponse,
  LinkChunksPayload,
  LinkChunksResponse,
  RawTextResponse,
  RelationTypeCatalogItem,
  SearchPayload,
  SearchResponse,
  UnlinkChunksPayload,
  UnlinkChunksResponse,
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
  async linkChunks(payload: LinkChunksPayload): Promise<LinkChunksResponse> {
    return this.request<LinkChunksResponse>('/documents/links', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async unlinkChunks(payload: UnlinkChunksPayload): Promise<UnlinkChunksResponse> {
    return this.request<UnlinkChunksResponse>('/documents/unlinks', {
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

  // 10. Corpus-wide Grep
  async grepCorpus(payload: CorpusGrepPayload): Promise<CorpusGrepResponse> {
    return this.request<CorpusGrepResponse>('/corpus/grep', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();
