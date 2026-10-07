import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { NavigationTabs, TabId } from './components/layout/NavigationTabs';
import { DocumentStudioContainer } from './components/studio/DocumentStudioContainer';
import { AuditHistoryDiff } from './components/diff/AuditHistoryDiff';
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
    addEdge,
    deleteEdge,
  } = useStagingSession();

  // Pre-flight check hook
  const {
    validationResult,
    validating,
    runValidation,
  } = usePreFlightCheck(activeDocSlug);

  // Modal / Selection state
  const [selectedStudioPath, setSelectedStudioPath] = useState<string>('');
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
          <DryRunSearchSimulator session={session} />
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
                onRefreshSession={async () => {
                  await refreshSessions();
                  if (activeDocSlug) await loadActiveSession(activeDocSlug);
                }}
              />
            )}

            {activeTab === 'dualview' && (
              <DualViewContainer
                session={session}
                selectedPath={selectedStudioPath}
                onSelectPath={setSelectedStudioPath}
              />
            )}

            {activeTab === 'graph' && (
              <VisualGraphInspector
                session={session}
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

      {/* Promotion Modal */}
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
