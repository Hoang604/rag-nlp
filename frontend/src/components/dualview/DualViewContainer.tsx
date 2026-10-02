import React, { useMemo, useState } from 'react';
import { Columns, Edit3, FileText, Search, Sparkles } from 'lucide-react';
import { StagingDocumentSession } from '../../types/staging';
import { DocumentTreeNode } from '../../types/tree';
import { StatutoryRawViewer } from './StatutoryRawViewer';
import { naturalLegalCompare } from '../../utils/sorting';

interface DualViewContainerProps {
  session: StagingDocumentSession;
  onEditChunk: (node: DocumentTreeNode) => void;
}

export const DualViewContainer: React.FC<DualViewContainerProps> = ({
  session,
  onEditChunk,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeChunkIndex, setActiveChunkIndex] = useState<number | null>(null);

  const chunks = useMemo(() => {
    return [...(session.chunks || [])].sort((a, b) =>
      naturalLegalCompare(a.path, b.path)
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

  const handleSelectChunk = (idx: number) => {
    setActiveChunkIndex(idx);
  };

  const handleLineClick = (lineNum: number) => {
    // Reverse lookup matching chunk spanning lineNum
    const matchedChunkIdx = chunks.findIndex(
      (c) => lineNum >= c.start_line && lineNum <= c.end_line
    );
    if (matchedChunkIdx !== -1) {
      setActiveChunkIndex(matchedChunkIdx);
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950 p-4">
      {/* Top Search Filter */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/90 p-3 shadow">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600/20 text-brand-400 border border-brand-500/30">
            <Columns className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">
              Đối Chiếu Song Song Toàn Văn (Dual View Synchronizer)
            </h3>
            <p className="text-[11px] text-slate-400">
              Bấm vào bất kỳ điều khoản nào bên phải để tự động cuộn và highlight văn bản gốc bên trái
            </p>
          </div>
        </div>

        <div className="relative min-w-[280px]">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Tìm kiếm đồng thời trong toàn văn & chunks..."
            className="w-full rounded-md border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-3 text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Split Screen Container */}
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-2">
        {/* Left Pane: Statutory Raw Text */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow">
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-bold text-slate-200">
                Toàn Văn Văn Bản Gốc ({rawLines.length} dòng)
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
            <StatutoryRawViewer
              rawText={session.raw_text || 'Chưa có văn bản nguyên văn đính kèm trong phiên staging này.'}
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
                Điều Khoản Đã Bóc Tách AST ({chunks.length} chunks)
              </span>
            </div>
            <span className="text-[11px] text-slate-400">
              Click để đồng bộ vị trí
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chunks.map((chunk, idx) => {
              const isSelected = activeChunkIndex === idx;
              const hasLineSpan = Boolean(chunk.start_line && chunk.end_line);

              return (
                <div
                  key={chunk.path}
                  onClick={() => handleSelectChunk(idx)}
                  style={{ contentVisibility: 'auto', containIntrinsicSize: '95px' }}
                  className={`cursor-pointer rounded-xl border p-4 transition-all duration-150 will-change-transform ${
                    isSelected
                      ? 'border-brand-500 bg-brand-950/40 ring-2 ring-brand-500/30 shadow-lg'
                      : 'border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900/90'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-slate-950 px-2.5 py-0.5 font-mono text-[11px] font-bold text-slate-200 border border-slate-800">
                        {chunk.path}
                      </span>
                      {hasLineSpan && (
                        <span className="rounded bg-brand-950/80 px-2 py-0.5 text-[10px] font-mono text-brand-400 border border-brand-800/80">
                          {chunk.start_line === chunk.end_line
                            ? `Dòng ${chunk.start_line}`
                            : `Dòng ${chunk.start_line} - ${chunk.end_line}`}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        title="Chỉnh sửa điều khoản"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditChunk({
                            path: chunk.path,
                            label: chunk.path,
                            node_type: 'NODE',
                            verbatim_text: chunk.verbatim_text,
                            contextualized_text: chunk.contextualized_text,
                            lead_sentence: chunk.lead_sentence || '',
                            start_line: chunk.start_line || 1,
                            end_line: chunk.end_line || 1,
                            metadata: chunk.metadata || {},
                            children: [],
                          });
                        }}
                        className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-brand-300 transition"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </button>
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
