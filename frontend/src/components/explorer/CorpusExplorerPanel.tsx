import React, { useState } from 'react';
import { FileText, RefreshCw, Search, Share2 } from 'lucide-react';
import { CorpusDocument, GraphVisualizerResponse } from '../../types/api';
import { DocumentTreeResponse } from '../../types/tree';
import { useI18n } from '../../i18n/I18nContext';
import { DocumentStudioContainer } from '../studio/DocumentStudioContainer';
import { VisualGraphInspector } from '../graph/VisualGraphInspector';

interface CorpusExplorerPanelProps {
  documents: CorpusDocument[];
  activeDocSlug: string;
  onSelectDoc: (slug: string) => void;
  treeData: DocumentTreeResponse | null;
  graphData: GraphVisualizerResponse | null;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  onRefresh: () => void;
  onOpenGlobalGrep: () => void;
}

export const CorpusExplorerPanel: React.FC<CorpusExplorerPanelProps> = ({
  documents,
  activeDocSlug,
  onSelectDoc,
  treeData,
  graphData,
  selectedPath,
  onSelectPath,
  onRefresh,
  onOpenGlobalGrep,
}) => {
  const { t } = useI18n();
  const [subMode, setSubMode] = useState<'studio' | 'graph'>('studio');

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950">
      {/* Compact Explorer Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/60 px-5 py-2 sm:px-8">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-400">
              {t('explorer.docSelect')}
            </span>
            <select
              data-testid="explorer-doc-select"
              value={activeDocSlug}
              onChange={(e) => onSelectDoc(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-medium text-slate-100 focus:border-brand-500 focus:outline-none"
            >
              {documents.map((doc) => (
                <option key={doc.doc_slug} value={doc.doc_slug}>
                  {doc.title} ({doc.doc_slug} — {doc.chunk_count} chunks)
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center rounded-lg border border-slate-800 bg-slate-950 p-0.5">
            <button
              type="button"
              data-testid="explorer-mode-studio"
              onClick={() => setSubMode('studio')}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                subMode === 'studio'
                  ? 'bg-brand-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="h-3.5 w-3.5" />
              <span>{t('explorer.mode.studio')}</span>
            </button>
            <button
              type="button"
              data-testid="explorer-mode-graph"
              onClick={() => setSubMode('graph')}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition ${
                subMode === 'graph'
                  ? 'bg-brand-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Share2 className="h-3.5 w-3.5" />
              <span>
                {t('explorer.mode.graph')} ({graphData?.edges?.length || 0})
              </span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenGlobalGrep}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-600"
          >
            <Search className="h-3.5 w-3.5 text-slate-400" />
            <span>{t('explorer.grep')}</span>
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-600"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t('explorer.refresh')}</span>
          </button>
        </div>
      </div>

      {/* Sub-mode Viewport */}
      <div className="flex-1 overflow-hidden">
        {subMode === 'studio' ? (
          <DocumentStudioContainer
            docSlug={activeDocSlug}
            treeData={treeData}
            edges={graphData?.edges || []}
            selectedPathProp={selectedPath}
            onSelectPathProp={onSelectPath}
            onRefresh={onRefresh}
          />
        ) : (
          <VisualGraphInspector
            docSlug={activeDocSlug}
            graphData={graphData}
            onSelectNode={(path) => {
              onSelectPath(path);
              setSubMode('studio');
            }}
          />
        )}
      </div>
    </div>
  );
};
