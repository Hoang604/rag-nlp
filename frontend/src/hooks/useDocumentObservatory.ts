import { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import {
  CorpusDocument,
  GraphVisualizerResponse,
  RawTextResponse,
} from '../types/api';
import { DocumentTreeResponse } from '../types/tree';

export function useDocumentObservatory() {
  const [documents, setDocuments] = useState<CorpusDocument[]>([]);
  const [activeDocSlug, setActiveDocSlug] = useState<string>('');
  const [treeData, setTreeData] = useState<DocumentTreeResponse | null>(null);
  const [graphData, setGraphData] = useState<GraphVisualizerResponse | null>(null);
  const [rawTextData, setRawTextData] = useState<RawTextResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
      if (docs.length > 0 && !activeDocSlug) {
        setActiveDocSlug(docs[0].doc_slug);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được danh sách tài liệu.');
    }
  }, [activeDocSlug]);

  const loadDocumentData = useCallback(async (slug: string) => {
    if (!slug) {
      setTreeData(null);
      setGraphData(null);
      setRawTextData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [tree, graph, raw] = await Promise.all([
        api.getDocumentTree(slug),
        api.getDocumentGraph(slug),
        api.getDocumentRaw(slug),
      ]);
      setTreeData(tree);
      setGraphData(graph);
      setRawTextData(raw);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi tải dữ liệu tài liệu.');
      setTreeData(null);
      setGraphData(null);
      setRawTextData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshDocuments();
  }, [refreshDocuments]);

  useEffect(() => {
    if (activeDocSlug) {
      void loadDocumentData(activeDocSlug);
    }
  }, [activeDocSlug, loadDocumentData]);

  const linkChunks = useCallback(
    async (sourcePath: string, targetPath: string, relationType: string) => {
      await api.linkChunks({
        source_path: sourcePath,
        target_path: targetPath,
        relation_type: relationType,
      });
      if (activeDocSlug) {
        await loadDocumentData(activeDocSlug);
      }
    },
    [activeDocSlug, loadDocumentData]
  );

  const unlinkChunks = useCallback(
    async (sourcePath: string, targetPath: string, relationType?: string) => {
      await api.unlinkChunks({
        source_path: sourcePath,
        target_path: targetPath,
        relation_type: relationType || null,
      });
      if (activeDocSlug) {
        await loadDocumentData(activeDocSlug);
      }
    },
    [activeDocSlug, loadDocumentData]
  );

  return {
    documents,
    activeDocSlug,
    setActiveDocSlug,
    treeData,
    graphData,
    rawTextData,
    loading,
    error,
    refreshDocuments,
    loadDocumentData,
    linkChunks,
    unlinkChunks,
  };
}
