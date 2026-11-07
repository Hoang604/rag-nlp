import React, { useState } from 'react';
import { AppHeader, TabId } from './components/layout/AppHeader';
import { LlmAnswerPanel } from './components/answer/LlmAnswerPanel';
import { EvalPanel } from './components/eval/EvalPanel';
import { CorpusExplorerPanel } from './components/explorer/CorpusExplorerPanel';
import { GlobalGrepModal } from './components/search/GlobalGrepModal';
import { ToastProvider } from './components/toast/ToastContext';
import { I18nProvider } from './i18n/I18nContext';
import { useDocumentObservatory } from './hooks/useDocumentObservatory';

const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('answer');

  const {
    documents,
    activeDocSlug,
    setActiveDocSlug,
    treeData,
    graphData,
    refreshDocuments,
    loadDocumentData,
  } = useDocumentObservatory();

  const [selectedStudioPath, setSelectedStudioPath] = useState<string>('');
  const [isGrepOpen, setIsGrepOpen] = useState(false);

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

  const handleOpenInExplorer = (docSlug: string, path: string) => {
    if (docSlug && docSlug !== activeDocSlug) {
      setActiveDocSlug(docSlug);
    }
    setSelectedStudioPath(path);
    setActiveTab('explorer');
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <AppHeader activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="relative flex-1 overflow-hidden">
        {activeTab === 'answer' && (
          <LlmAnswerPanel
            documents={documents}
            onOpenInExplorer={handleOpenInExplorer}
          />
        )}

        {activeTab === 'eval' && <EvalPanel />}

        {activeTab === 'explorer' && (
          <CorpusExplorerPanel
            documents={documents}
            activeDocSlug={activeDocSlug}
            onSelectDoc={setActiveDocSlug}
            treeData={treeData}
            graphData={graphData}
            selectedPath={selectedStudioPath}
            onSelectPath={setSelectedStudioPath}
            onRefresh={async () => {
              await refreshDocuments();
              if (activeDocSlug) {
                await loadDocumentData(activeDocSlug);
              }
            }}
            onOpenGlobalGrep={() => setIsGrepOpen(true)}
          />
        )}
      </main>

      <GlobalGrepModal
        isOpen={isGrepOpen}
        onClose={() => setIsGrepOpen(false)}
        docSlug={activeDocSlug}
        onSelectHit={(path, hitDocSlug) => {
          handleOpenInExplorer(hitDocSlug || activeDocSlug, path);
        }}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <I18nProvider>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </I18nProvider>
  );
};

export default App;
