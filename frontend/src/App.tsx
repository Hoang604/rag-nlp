import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { NavigationTabs, TabId } from './components/layout/NavigationTabs';
import { DocumentStudioContainer } from './components/studio/DocumentStudioContainer';
import { VisualGraphInspector } from './components/graph/VisualGraphInspector';
import { DryRunSearchSimulator } from './components/search/DryRunSearchSimulator';
import { GlobalGrepModal } from './components/search/GlobalGrepModal';
import { ToastProvider } from './components/toast/ToastContext';
import { useDocumentObservatory } from './hooks/useDocumentObservatory';

const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('studio');

  // Corpus Observatory Hook
  const {
    documents,
    activeDocSlug,
    setActiveDocSlug,
    treeData,
    graphData,
    refreshDocuments,
    loadDocumentData,
  } = useDocumentObservatory();

  // Modal / Selection state
  const [selectedStudioPath, setSelectedStudioPath] = useState<string>('');
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

  const edgesCount = graphData?.edges?.length || 0;
  const chunksCount = treeData?.total_chunks || 0;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Global Header */}
      <Header
        documents={documents}
        showDocPicker={activeTab !== 'search'}
        activeDocSlug={activeDocSlug}
        onSelectDoc={setActiveDocSlug}
        onRefresh={async () => {
          await refreshDocuments();
          if (activeDocSlug) {
            await loadDocumentData(activeDocSlug);
          }
        }}
        onOpenGlobalGrep={() => setIsGrepOpen(true)}
      />

      {/* Primary Navigation Tabs */}
      <NavigationTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        chunksCount={chunksCount}
        edgesCount={edgesCount}
      />

      {/* Main Subsystem Body */}
      <main className="relative flex-1 overflow-hidden">
        {activeTab === 'search' ? (
          <DryRunSearchSimulator activeDocSlug={activeDocSlug} />
        ) : !activeDocSlug ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center max-w-sm p-6">
              <p className="text-sm text-slate-400 mb-2">
                Chưa có tài liệu nào trong PostgreSQL production.
              </p>
              <p className="text-xs text-slate-500 font-mono">
                Sử dụng lệnh CLI `rag-eval ingest &lt;file&gt;` để nạp tài liệu trực tiếp vào hệ thống.
              </p>
            </div>
          </div>
        ) : (
          <>
            {activeTab === 'studio' && (
              <DocumentStudioContainer
                docSlug={activeDocSlug}
                treeData={treeData}
                edges={graphData?.edges || []}
                selectedPathProp={selectedStudioPath}
                onSelectPathProp={setSelectedStudioPath}
                onRefresh={async () => {
                  if (activeDocSlug) await loadDocumentData(activeDocSlug);
                }}
              />
            )}

            {activeTab === 'graph' && (
              <VisualGraphInspector
                docSlug={activeDocSlug}
                graphData={graphData}
                onSelectNode={(path) => {
                  setSelectedStudioPath(path);
                  setActiveTab('studio');
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Global In-Memory Grep Search Modal */}
      <GlobalGrepModal
        isOpen={isGrepOpen}
        onClose={() => setIsGrepOpen(false)}
        docSlug={activeDocSlug}
        onSelectHit={(path) => {
          setSelectedStudioPath(path);
          setActiveTab('studio');
        }}
      />
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
