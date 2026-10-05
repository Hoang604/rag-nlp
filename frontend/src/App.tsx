import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { NavigationTabs, TabId } from './components/layout/NavigationTabs';
import { DocumentStudioContainer } from './components/studio/DocumentStudioContainer';
import { AuditHistoryDiff } from './components/diff/AuditHistoryDiff';
import { SurgicalEditorDrawer } from './components/editor/SurgicalEditorDrawer';
import { AddChunkModal } from './components/editor/AddChunkModal';
import { DeleteConfirmModal } from './components/editor/DeleteConfirmModal';
import { VisualGraphInspector } from './components/graph/VisualGraphInspector';
import { DualViewContainer } from './components/dualview/DualViewContainer';
import { PreFlightChecklist } from './components/checklist/PreFlightChecklist';
import { PromotionModal } from './components/checklist/PromotionModal';
import { CreateSessionModal } from './components/upload/CreateSessionModal';
import { DryRunSearchSimulator } from './components/search/DryRunSearchSimulator';
import { UnresolvedBacklogModal } from './components/studio/UnresolvedBacklogModal';
import { GlobalGrepModal } from './components/search/GlobalGrepModal';
import { ToastProvider, useToast } from './components/toast/ToastContext';
import { useStagingSession } from './hooks/useStagingSession';
import { usePreFlightCheck } from './hooks/usePreFlightCheck';
import { DocumentTreeNode } from './types/tree';
import { StagingChunk } from './types/staging';
import { api } from './services/api';

const AppContent: React.FC = () => {
  const { success, error } = useToast();
  const [activeTab, setActiveTab] = useState<TabId>('studio');

  // Staging session hook
  const {
    sessions,
    activeDocSlug,
    setActiveDocSlug,
    session,
    treeData,
    refreshSessions,
    loadActiveSession,
    patchChunks,
    finalizeChunks,
    unfinalizeChunks,
    addEdge,
    deleteEdge,
  } = useStagingSession();

  // Pre-flight check hook
  const {
    validationResult,
    validating,
    runValidation,
  } = usePreFlightCheck(activeDocSlug);

  // Modal / Drawer state
  const [selectedStudioPath, setSelectedStudioPath] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<DocumentTreeNode | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addParentPath, setAddParentPath] = useState('');
  const [deleteTargetChunk, setDeleteTargetChunk] = useState<string | null>(null);
  const [isPromotionOpen, setIsPromotionOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isBacklogOpen, setIsBacklogOpen] = useState(false);
  const [isGrepOpen, setIsGrepOpen] = useState(false);

  // Global shortcut for Ctrl+K
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsGrepOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Chunk handlers
  const handleToggleFinalizeChunk = async (node: DocumentTreeNode) => {
    // DEF-INGEST-002: Include both the section node itself and all its descendant nodes
    const collectAllPaths = (n: DocumentTreeNode): string[] => {
      const paths = [n.path];
      if (n.children && n.children.length > 0) {
        n.children.forEach((c) => paths.push(...collectAllPaths(c)));
      }
      return paths;
    };
    const targetPaths = collectAllPaths(node);
    const isCurrentlyReviewed = node.review_status === 'REVIEWED';
    try {
      if (isCurrentlyReviewed) {
        const ok = await unfinalizeChunks(targetPaths);
        if (ok) {
          success(
            'Đã mở lại chunk',
            `Đã chuyển ${targetPaths.length} mục sang Chờ rà soát.`
          );
        }
      } else {
        const ok = await finalizeChunks(targetPaths);
        if (ok) {
          success(
            'Rà soát chunk thành công',
            `Đã cập nhật trạng thái đã rà soát cho ${targetPaths.length} mục.`
          );
        }
      }
    } catch (err) {
      error('Lỗi cập nhật trạng thái', err instanceof Error ? err.message : 'Lỗi hệ thống');
    }
  };

  const handleEditChunk = (node: DocumentTreeNode) => {
    setSelectedNode(node);
    setIsEditorOpen(true);
  };

  const handleDeleteChunkConfirm = async () => {
    if (!deleteTargetChunk) return;
    try {
      await patchChunks([], [deleteTargetChunk]);
      success('Đã xóa chunk', `Đã loại bỏ ${deleteTargetChunk} khỏi Staging.`);
    } catch (err) {
      error('Lỗi xóa chunk', err instanceof Error ? err.message : 'Lỗi hệ thống');
    } finally {
      setDeleteTargetChunk(null);
    }
  };

  const handleAddChildChunk = (parentPath: string) => {
    setAddParentPath(parentPath);
    setIsAddModalOpen(true);
  };

  const handleSaveChunk = async (chunk: StagingChunk) => {
    const ok = await patchChunks([chunk], []);
    if (ok) {
      success('Lưu thành công', `Đã cập nhật chunk ${chunk.path}.`);
    }
    return ok;
  };

  const handleAddChunkDirect = async (chunk: StagingChunk) => {
    const ok = await patchChunks([chunk], []);
    if (ok) {
      success('Thêm thành công', `Đã tạo chunk mới ${chunk.path}.`);
    }
    return ok;
  };

  const handleReopenSession = async () => {
    if (!activeDocSlug) return;
    try {
      await api.reopenSession(activeDocSlug);
      await refreshSessions();
      success(
        'Đã mở lại phiên làm việc',
        `Tài liệu ${activeDocSlug} đã chuyển sang trạng thái AMENDMENT để sửa đổi.`
      );
    } catch (err: unknown) {
      error('Không thể mở lại phiên', err instanceof Error ? err.message : String(err));
    }
  };

  const handleDeleteSession = async () => {
    if (!session) return;
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn hủy và xóa vĩnh viễn phiên làm việc '${session.doc_slug}' khỏi Vùng đệm Staging?`
    );
    if (!confirmed) return;
    try {
      await api.deleteSession(session.doc_slug);
      success('Đã xóa phiên', `Phiên làm việc '${session.doc_slug}' đã được loại bỏ.`);
      await refreshSessions();
      setActiveDocSlug('');
    } catch (err) {
      error('Lỗi khi xóa phiên', err instanceof Error ? err.message : String(err));
    }
  };

  const handleBatchFinalize = async (paths: string[]) => {
    try {
      const ok = await finalizeChunks(paths);
      if (ok) {
        success('Rà soát hoàn tất', `Đã cập nhật đã rà soát cho ${paths.length} mục.`);
      }
    } catch (err) {
      error('Lỗi rà soát hàng loạt', err instanceof Error ? err.message : String(err));
    }
  };

  const handleBatchReopen = async (paths: string[]) => {
    try {
      const ok = await unfinalizeChunks(paths);
      if (ok) {
        success('Đã mở lại', `Đã chuyển ${paths.length} mục sang Chờ rà soát.`);
      }
    } catch (err) {
      error('Lỗi mở lại', err instanceof Error ? err.message : String(err));
    }
  };

  const handleBatchDelete = async (paths: string[]) => {
    const confirmed = window.confirm(`Bạn có chắc chắn muốn xóa ${paths.length} mục đã chọn khỏi Staging?`);
    if (!confirmed) return;
    try {
      await patchChunks([], paths);
      success('Đã xóa', `Đã loại bỏ ${paths.length} mục khỏi Staging.`);
    } catch (err) {
      error('Lỗi xóa hàng loạt', err instanceof Error ? err.message : String(err));
    }
  };

  const blockingCount =
    validationResult?.issues?.filter((i) => i.blocking)?.length || 0;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Global Header */}
      <Header
        sessions={sessions}
        showDocPicker={activeTab !== 'search'}
        activeDocSlug={activeDocSlug}
        session={session}
        onSelectDoc={setActiveDocSlug}
        onRefresh={refreshSessions}
        onOpenPromotionModal={() => setIsPromotionOpen(true)}
        onOpenCreateSessionModal={() => setIsCreateOpen(true)}
        onQuickValidate={runValidation}
        onReopenSession={handleReopenSession}
        onDeleteSession={handleDeleteSession}
        onOpenBacklogModal={() => setIsBacklogOpen(true)}
        onOpenGlobalGrep={() => setIsGrepOpen(true)}
        validating={validating}
        blockingIssuesCount={blockingCount}
      />

      {/* Primary Navigation Tabs */}
      <NavigationTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        chunksCount={session?.chunks?.length || 0}
        edgesCount={session?.edges?.length || 0}
        diffsCount={session?.mutation_history?.length || 0}
        issuesCount={blockingCount}
      />

      {/* Main Subsystem Body */}
      <main className="relative flex-1 overflow-hidden">
        {activeTab === 'search' ? (
          <DryRunSearchSimulator session={session} onEditChunk={handleEditChunk} />
        ) : !session ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center max-w-sm p-6">
              <p className="text-sm text-slate-400 mb-4">
                Chưa có tài liệu nào được chọn hoặc Vùng đệm Staging đang trống.
              </p>
              <button
                type="button"
                onClick={() => setIsCreateOpen(true)}
                className="rounded-xl bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-brand-950 hover:from-brand-500 hover:to-brand-600 transition"
              >
                + Tải Lên &amp; Bóc Tách Tài Liệu Mới
              </button>
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'studio' && (
              <DocumentStudioContainer
                session={session}
                treeData={treeData}
                selectedPathProp={selectedStudioPath}
                onSelectPathProp={setSelectedStudioPath}
                onEditChunk={handleEditChunk}
                onDeleteChunk={(path) => setDeleteTargetChunk(path)}
                onAddChildChunk={handleAddChildChunk}
                onAddEdge={addEdge}
                onToggleFinalizeChunk={handleToggleFinalizeChunk}
                onRefreshSession={async () => {
                  await refreshSessions();
                  if (activeDocSlug) await loadActiveSession(activeDocSlug);
                }}
                onBatchFinalizeChunks={handleBatchFinalize}
                onBatchReopenChunks={handleBatchReopen}
                onBatchDeleteChunks={handleBatchDelete}
              />
            )}

            {activeTab === 'dualview' && (
              <DualViewContainer
                session={session}
                onEditChunk={handleEditChunk}
                onToggleFinalizeChunk={handleToggleFinalizeChunk}
                selectedPath={selectedStudioPath}
                onSelectPath={setSelectedStudioPath}
              />
            )}

            {activeTab === 'graph' && (
              <VisualGraphInspector
                session={session}
                onAddEdge={addEdge}
                onDeleteEdge={deleteEdge}
                onSelectNode={(path) => {
                  setSelectedStudioPath(path);
                  setActiveTab('studio');
                }}
              />
            )}

            {activeTab === 'diff' && (
              <AuditHistoryDiff
                session={session}
                onRefreshSession={async () => {
                  await refreshSessions();
                  if (activeDocSlug) await loadActiveSession(activeDocSlug);
                }}
              />
            )}

            {activeTab === 'checklist' && (
              <PreFlightChecklist
                session={session}
                validationResult={validationResult}
                validating={validating}
                onReValidate={runValidation}
                onOpenPromotionModal={() => setIsPromotionOpen(true)}
                onNavigateToNode={(path) => {
                  setSelectedStudioPath(path);
                  setActiveTab('studio');
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Modals and Drawers */}
      <SurgicalEditorDrawer
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        selectedNode={selectedNode}
        onSaveChunk={handleSaveChunk}
      />

      <AddChunkModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddChunkDirect}
        parentPath={addParentPath}
      />

      <DeleteConfirmModal
        isOpen={deleteTargetChunk !== null}
        onClose={() => setDeleteTargetChunk(null)}
        onConfirm={handleDeleteChunkConfirm}
        path={deleteTargetChunk || ''}
      />

      {session && (
        <PromotionModal
          isOpen={isPromotionOpen}
          onClose={() => setIsPromotionOpen(false)}
          session={session}
          onPromote={async (payload) => {
            const res = await api.promoteSession(session.doc_slug, payload);
            await refreshSessions();
            if (session.doc_slug) {
              await loadActiveSession(session.doc_slug);
            }
            return res;
          }}
        />
      )}

      {/* Dedicated Upload & Ingestion Modal */}
      <CreateSessionModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={async (newSlug) => {
          await refreshSessions();
          setActiveDocSlug(newSlug);
        }}
      />

      {/* Unresolved Backlog Drawer / Modal */}
      <UnresolvedBacklogModal
        isOpen={isBacklogOpen}
        onClose={() => setIsBacklogOpen(false)}
        session={session}
        onAddEdge={addEdge}
        onDeleteEdge={deleteEdge}
        onSelectChunk={(path) => {
          setSelectedStudioPath(path);
          setActiveTab('studio');
          setIsBacklogOpen(false);
        }}
      />

      {/* Global In-Memory Grep Search Modal */}
      {session && (
        <GlobalGrepModal
          isOpen={isGrepOpen}
          onClose={() => setIsGrepOpen(false)}
          docSlug={session.doc_slug}
          onSelectHit={(path) => {
            setSelectedStudioPath(path);
            setActiveTab('studio');
          }}
        />
      )}
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
};

export default App;
