import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Columns, FileText, Filter, Search, Sparkles } from 'lucide-react';
import { StagingDocumentSession } from '../../types/staging';
import { SourceTextViewer } from './SourceTextViewer';
import { naturalPathCompare } from '../../utils/sorting';
import { api } from '../../services/api';

interface DualViewContainerProps {
  session: StagingDocumentSession;
  selectedPath?: string;
  onSelectPath?: (path: string) => void;
}

export const DualViewContainer: React.FC<DualViewContainerProps> = ({
  session,
  selectedPath,
  onSelectPath,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isRegex, setIsRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [searchIn, setSearchIn] = useState('ALL');
  const [activeChunkIndex, setActiveChunkIndex] = useState<number | null>(null);
  const [grepHitPaths, setGrepHitPaths] = useState<Set<string> | null>(null);
  const [isGrepRunning, setIsGrepRunning] = useState(false);

  const chunkRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const chunks = useMemo(() => {
    return [...(session.chunks || [])].sort((a, b) =>
      naturalPathCompare(a.path, b.path)
    );
  }, [session.chunks]);

  const rawLines = useMemo(
    () => (session.raw_text || '').split('\n').map((l) => l.replace(/\r$/, '')),
    [session.raw_text]
  );

  const activeRange = useMemo(() => {
    if (activeChunkIndex === null || !chunks[activeChunkIndex]) return null;
    const chunk = chunks[activeChunkIndex];
    if (chunk.start_line && chunk.end_line) {
      return { start: chunk.start_line, end: chunk.end_line };
    }
    return null;
  }, [activeChunkIndex, chunks]);

  // Two-way scroll sync: when activeChunkIndex updates, scroll right pane to chunk card
  useEffect(() => {
    if (activeChunkIndex !== null) {
      const el = chunkRefs.current.get(activeChunkIndex);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeChunkIndex]);

  // In-memory grep trigger when regex or advanced filter is active
  useEffect(() => {
    if (!searchTerm.trim()) {
      setGrepHitPaths(null);
      return;
    }

    let isMounted = true;
    const timer = setTimeout(async () => {
      try {
        setIsGrepRunning(true);
        const res = await api.grepSession(session.doc_slug, {
          pattern: searchTerm.trim(),
          is_regex: isRegex,
          case_sensitive: caseSensitive,
          search_in: searchIn,
        });
        if (isMounted) {
          const hitSet = new Set(res.hits.map((h) => h.path));
          setGrepHitPaths(hitSet);
          // If first match found, select it
          if (res.hits.length > 0) {
            const firstIdx = chunks.findIndex((c) => c.path === res.hits[0].path);
            if (firstIdx !== -1) {
              setActiveChunkIndex(firstIdx);
            }
          }
        }
      } catch {
        if (isMounted) setGrepHitPaths(null);
      } finally {
        if (isMounted) setIsGrepRunning(false);
      }
    }, 250);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [searchTerm, isRegex, caseSensitive, searchIn, session.doc_slug, chunks]);

  // Sync external selectedPath into activeChunkIndex
  useEffect(() => {
    if (selectedPath) {
      const idx = chunks.findIndex((c) => c.path === selectedPath);
      if (idx !== -1) {
        setActiveChunkIndex(idx);
      }
    }
  }, [selectedPath, chunks]);

  const handleSelectChunk = (idx: number) => {
    setActiveChunkIndex(idx);
    if (chunks[idx]) {
      onSelectPath?.(chunks[idx].path);
    }
  };

  const handleLineClick = (lineNum: number) => {
    // Reverse lookup matching chunk spanning lineNum with two-way scroll
    const matchedChunkIdx = chunks.findIndex(
      (c) => lineNum >= (c.start_line || 1) && lineNum <= (c.end_line || 1)
    );
    if (matchedChunkIdx !== -1) {
      setActiveChunkIndex(matchedChunkIdx);
      if (chunks[matchedChunkIdx]) {
        onSelectPath?.(chunks[matchedChunkIdx].path);
      }
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950 p-4">
      {/* Top Search & In-Memory Grep Bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/90 p-3 shadow">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600/20 text-brand-400 border border-brand-500/30">
            <Columns className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">
              Đối Chiếu Song Song Toàn Văn &amp; Regex Grep
            </h3>
            <p className="text-[11px] text-slate-400">
              Đồng bộ 2 chiều: click dòng ở tài liệu gốc để cuộn tới chunk tương ứng, hoặc ngược lại
            </p>
          </div>
        </div>

        {/* In-Memory Grep Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative min-w-[240px] sm:min-w-[280px]">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Grep tìm kiếm (chữ hoặc biểu thức regex)..."
              className="w-full rounded-md border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-16 text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
            />
            {isGrepRunning && (
              <span className="absolute right-2.5 top-2 text-[10px] font-mono text-brand-400 animate-pulse">
                Đang grep...
              </span>
            )}
            {grepHitPaths !== null && !isGrepRunning && (
              <span className="absolute right-2.5 top-2 text-[10px] font-mono text-emerald-400 font-bold">
                {grepHitPaths.size} hits
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsRegex(!isRegex)}
            title="Bật/Tắt Biểu thức chính quy (Regex)"
            className={`rounded px-2 py-1 text-xs font-mono font-bold transition border ${
              isRegex
                ? 'border-brand-500 bg-brand-950 text-brand-300'
                : 'border-slate-800 bg-slate-950 text-slate-500 hover:text-slate-300'
            }`}
          >
            .*
          </button>

          <button
            type="button"
            onClick={() => setCaseSensitive(!caseSensitive)}
            title="Phân biệt hoa/thường"
            className={`rounded px-2 py-1 text-xs font-mono font-bold transition border ${
              caseSensitive
                ? 'border-brand-500 bg-brand-950 text-brand-300'
                : 'border-slate-800 bg-slate-950 text-slate-500 hover:text-slate-300'
            }`}
          >
            Aa
          </button>

          <div className="flex items-center gap-1 rounded border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-400">
            <Filter className="h-3 w-3" />
            <select
              value={searchIn}
              onChange={(e) => setSearchIn(e.target.value)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none"
            >
              <option value="ALL">Toàn bộ</option>
              <option value="VERBATIM">Verbatim Text</option>
              <option value="CONTEXT">Context Header</option>
              <option value="PATH">LTree Path</option>
              <option value="METADATA">Metadata</option>
            </select>
          </div>
        </div>
      </div>

      {/* Split Screen Container */}
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-2">
        {/* Left Pane: Raw Document Text */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow">
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-bold text-slate-200">
                Nội Dung Tài Liệu Gốc ({rawLines.length} dòng)
              </span>
            </div>
            {activeRange !== null && (
              <span className="rounded bg-brand-950 px-2 py-0.5 font-mono text-[10px] font-bold text-brand-400 border border-brand-800">
                {activeRange.start === activeRange.end
                  ? `Đang khớp: Dòng ${activeRange.start}`
                  : `Đang khớp: Dòng ${activeRange.start} - ${activeRange.end}`}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden p-2">
            <SourceTextViewer
              rawText={session.raw_text || 'Chưa có nội dung nguyên văn đính kèm trong phiên staging này.'}
              searchTerm={searchTerm}
              highlightRange={activeRange}
              onLineClick={handleLineClick}
            />
          </div>
        </div>

        {/* Right Pane: Parsed Chunks Stream */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow">
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-400" />
              <span className="text-xs font-bold text-slate-200">
                Mục Nội Dung Đã Bóc Tách AST ({chunks.length} chunks)
              </span>
            </div>
            <span className="text-[11px] text-slate-400">
              Click để đồng bộ vị trí
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chunks.map((chunk, idx) => {
              const isSelected = activeChunkIndex === idx;
              const isGrepHit = grepHitPaths ? grepHitPaths.has(chunk.path) : false;
              const hasLineSpan = Boolean(chunk.start_line && chunk.end_line);

              return (
                <div
                  key={chunk.path}
                  ref={(el) => {
                    if (el) chunkRefs.current.set(idx, el);
                    else chunkRefs.current.delete(idx);
                  }}
                  onClick={() => handleSelectChunk(idx)}
                  style={{ contentVisibility: 'auto', containIntrinsicSize: '95px' }}
                  className={`cursor-pointer rounded-xl border p-4 transition-all duration-150 will-change-transform ${
                    isSelected
                      ? 'border-brand-500 bg-brand-950/40 ring-2 ring-brand-500/30 shadow-lg'
                      : isGrepHit
                      ? 'border-amber-500/80 bg-amber-950/20 ring-1 ring-amber-500/30'
                      : 'border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900/90'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-slate-950 px-2.5 py-0.5 font-mono text-[11px] font-bold text-slate-200 border border-slate-800">
                        {chunk.path}
                      </span>
                      <span
                        className={`rounded border px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider ${
                          chunk.review_status === 'REVIEWED'
                            ? 'border-emerald-600/60 bg-emerald-950/80 text-emerald-300'
                            : 'border-amber-600/60 bg-amber-950/80 text-amber-300'
                        }`}
                      >
                        {chunk.review_status === 'REVIEWED' ? 'ĐÃ RÀ SOÁT' : 'CHỜ RÀ SOÁT'}
                      </span>
                      {hasLineSpan && (
                        <span className="rounded bg-brand-950/80 px-2 py-0.5 text-[10px] font-mono text-brand-400 border border-brand-800/80">
                          {chunk.start_line === chunk.end_line
                            ? `Dòng ${chunk.start_line}`
                            : `Dòng ${chunk.start_line} - ${chunk.end_line}`}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                    {chunk.verbatim_text}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
