import { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import {
  BatchPatchPayload,
  CreateEdgePayload,
  DeleteEdgePayload,
} from '../types/api';
import {
  StagingChunk,
  StagingDocumentSession,
  StagingSessionSummary,
  StagingStatus,
} from '../types/staging';
import { DocumentTreeResponse } from '../types/tree';

export function useStagingSession(initialDocSlug?: string) {
  const [sessions, setSessions] = useState<StagingSessionSummary[]>([]);
  const [activeDocSlug, setActiveDocSlug] = useState<string | undefined>(
    initialDocSlug
  );
  const [session, setSession] = useState<StagingDocumentSession | null>(null);
  const [treeData, setTreeData] = useState<DocumentTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [treeLoading, setTreeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load list of all sessions
  const refreshSessions = useCallback(async () => {
    try {
      const list = await api.listSessions();
      setSessions(list);
      if (!activeDocSlug && list.length > 0) {
        setActiveDocSlug(list[0].doc_slug);
      }
      return list;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Lỗi tải danh sách văn bản';
      setError(msg);
      return [];
    }
  }, [activeDocSlug]);

  // Load active session detail and tree hierarchy
  const loadActiveSession = useCallback(async (docSlug: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSession(docSlug);
      setSession(data);
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : `Lỗi tải văn bản ${docSlug}`;
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTreeHierarchy = useCallback(async (docSlug: string) => {
    setTreeLoading(true);
    try {
      const tree = await api.getDocumentTree(docSlug);
      setTreeData(tree);
      return tree;
    } catch (err) {
      console.error('Failed to load tree:', err);
      return null;
    } finally {
      setTreeLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  // Sync when activeDocSlug changes
  useEffect(() => {
    if (activeDocSlug) {
      void loadActiveSession(activeDocSlug);
      void loadTreeHierarchy(activeDocSlug);
    } else {
      setSession(null);
      setTreeData(null);
    }
  }, [activeDocSlug, loadActiveSession, loadTreeHierarchy]);

  // Mutation helper: patch chunks in-place
  const patchChunks = useCallback(
    async (updatedChunks: StagingChunk[], removedPaths: string[] = []) => {
      if (!activeDocSlug) return false;
      try {
        const payload: BatchPatchPayload = {
          updated_chunks: updatedChunks,
          removed_paths: removedPaths,
        };
        await api.patchChunks(activeDocSlug, payload);
        await loadActiveSession(activeDocSlug);
        await loadTreeHierarchy(activeDocSlug);
        await refreshSessions();
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi cập nhật điều khoản';
        setError(msg);
        return false;
      }
    },
    [activeDocSlug, loadActiveSession, loadTreeHierarchy, refreshSessions]
  );

  // Mutation helper: add edge
  const addEdge = useCallback(
    async (edge: CreateEdgePayload) => {
      if (!activeDocSlug) return false;
      try {
        await api.addEdges(activeDocSlug, [edge]);
        await loadActiveSession(activeDocSlug);
        await refreshSessions();
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi thêm quan hệ pháp lý';
        setError(msg);
        return false;
      }
    },
    [activeDocSlug, loadActiveSession, refreshSessions]
  );

  // Mutation helper: delete edge
  const deleteEdge = useCallback(
    async (payload: DeleteEdgePayload) => {
      if (!activeDocSlug) return false;
      try {
        await api.deleteEdge(activeDocSlug, payload);
        await loadActiveSession(activeDocSlug);
        await refreshSessions();
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi xóa quan hệ pháp lý';
        setError(msg);
        return false;
      }
    },
    [activeDocSlug, loadActiveSession, refreshSessions]
  );

  // Mutation helper: update status
  const updateStatus = useCallback(
    async (status: StagingStatus, actor = 'HUMAN:reviewer', description = '') => {
      if (!activeDocSlug) return false;
      try {
        await api.updateSessionStatus(activeDocSlug, status, actor, description);
        await loadActiveSession(activeDocSlug);
        await refreshSessions();
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi chuyển trạng thái';
        setError(msg);
        return false;
      }
    },
    [activeDocSlug, loadActiveSession, refreshSessions]
  );

  // Mutation helper: finalize chunks
  const finalizeChunks = useCallback(
    async (paths: string[]) => {
      if (!activeDocSlug) return false;
      try {
        await api.finalizeChunks(activeDocSlug, paths);
        await loadActiveSession(activeDocSlug);
        await loadTreeHierarchy(activeDocSlug);
        await refreshSessions();
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Lỗi chốt điều khoản';
        setError(msg);
        return false;
      }
    },
    [activeDocSlug, loadActiveSession, loadTreeHierarchy, refreshSessions]
  );

  return {
    sessions,
    activeDocSlug,
    setActiveDocSlug,
    session,
    treeData,
    loading,
    treeLoading,
    error,
    setError,
    refreshSessions,
    loadActiveSession,
    loadTreeHierarchy,
    patchChunks,
    finalizeChunks,
    addEdge,
    deleteEdge,
    updateStatus,
  };
}
