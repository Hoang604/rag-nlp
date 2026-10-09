import React, { useState } from 'react';
import {
  Layers,
  RefreshCw,
  Scale,
  Search,
} from 'lucide-react';
import { CorpusDocument } from '../../types/api';
import { StatusBadge } from './StatusBadge';

interface HeaderProps {
  showDocPicker?: boolean;
  documents: CorpusDocument[];
  activeDocSlug?: string;
  onSelectDoc: (docSlug: string) => void;
  onRefresh: () => void;
  onOpenGlobalGrep?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  showDocPicker = true,
  documents,
  activeDocSlug,
  onSelectDoc,
  onRefresh,
  onOpenGlobalGrep,
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const activeDoc = documents.find((d) => d.doc_slug === activeDocSlug);

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/95 px-5 py-3 shadow-md">
      {/* Brand & Document Selector */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-inner">
            <Scale className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-wide text-slate-100">
                CORPUS OBSERVATORY
              </span>
              <span className="rounded bg-brand-950 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-brand-400 border border-brand-800/60">
                v2.0 Direct
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Knowledge Graph &amp; Corpus Observatory
            </p>
          </div>
        </div>

        {showDocPicker && (
          <>
            <div className="h-6 w-px bg-slate-800 hidden sm:block" />

            {/* Document Selection Dropdown */}
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-slate-400" />
              <select
                value={activeDocSlug || ''}
                onChange={(e) => onSelectDoc(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs md:text-sm font-medium text-slate-100 shadow-sm transition hover:border-slate-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {documents.length === 0 ? (
                  <option value="">Chưa có tài liệu trong PostgreSQL</option>
                ) : (
                  documents.map((d) => (
                    <option key={d.doc_slug} value={d.doc_slug}>
                      {d.doc_slug} — {d.title.substring(0, 38)}
                      {d.title.length > 38 ? '...' : ''} ({d.chunk_count} mục)
                    </option>
                  ))
                )}
              </select>

              <button
                onClick={handleRefresh}
                title="Làm mới danh sách tài liệu"
                className="rounded-lg border border-slate-700 bg-slate-800 p-2 text-slate-300 transition hover:bg-slate-700 hover:text-white"
              >
                <RefreshCw
                  className={`h-4 w-4 ${isRefreshing ? 'animate-spin text-brand-400' : ''}`}
                />
              </button>
            </div>
          </>
        )}
      </div>

      {/* Center / Right Metadata & Action Buttons */}
      <div className="flex items-center gap-3">
        {/* Global Grep Search Button */}
        {onOpenGlobalGrep && (
          <button
            type="button"
            onClick={onOpenGlobalGrep}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition"
            title="Tìm kiếm toàn văn pg_trgm (Ctrl+K)"
          >
            <Search className="h-3.5 w-3.5 text-brand-400" />
            <span className="hidden sm:inline">Tìm kiếm</span>
            <span className="hidden md:inline rounded bg-slate-900 px-1 py-0.2 text-[9px] font-mono text-slate-400 border border-slate-750">
              Ctrl+K
            </span>
          </button>
        )}

        {/* Document Metadata Chip */}
        {activeDoc && (
          <div className="hidden xl:flex items-center gap-2 rounded-lg bg-slate-800/80 px-2.5 py-1 border border-slate-700 text-[11px] text-slate-300 font-mono">
            <span className="font-bold text-brand-300">
              {activeDoc.doc_slug}
            </span>
            <span className="text-slate-600">•</span>
            <span>{activeDoc.chunk_count} chunks</span>
          </div>
        )}

        <StatusBadge status="POSTGRESQL LIVE" />
      </div>
    </header>
  );
};
