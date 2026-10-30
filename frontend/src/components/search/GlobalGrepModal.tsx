import React, { useEffect, useRef, useState } from 'react';
import {
  Search,
  X,
} from 'lucide-react';
import { api } from '../../services/api';

interface GlobalGrepModalProps {
  isOpen: boolean;
  onClose: () => void;
  docSlug?: string;
  onSelectHit: (path: string, docSlug: string) => void;
}

export const GlobalGrepModal: React.FC<GlobalGrepModalProps> = ({
  isOpen,
  onClose,
  onSelectHit,
}) => {
  const [pattern, setPattern] = useState('');
  const [isRegex, setIsRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<
    Array<{
      path: string;
      doc_slug?: string;
      field_matched: string;
      match_snippet: string;
      verbatim_text: string;
    }>
  >([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Execute Grep
  useEffect(() => {
    if (!isOpen || !pattern.trim()) {
      setResults([]);
      setErrorMsg(null);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const resp = await api.search({
          query: pattern,
          pattern: pattern,
          is_regex: isRegex,
          case_sensitive: caseSensitive,
          order_by_reading_order: true,
          limit: 30,
        });
        const allHits = (resp.groups ?? []).flatMap((g) =>
          g.provisions
            .filter((p) => p.found_in === 'both' || p.found_in === 'verbatim_only')
            .map((p) => ({
              path: p.path,
              doc_slug: g.doc_slug,
              field_matched: `LINE ${p.start_line}-${p.end_line}`,
              match_snippet: p.text.substring(0, 150),
              verbatim_text: p.text,
            }))
        );
        setResults(allHits);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [pattern, isRegex, caseSensitive, isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/75 p-4 sm:p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden mt-12 animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-3.5 bg-slate-950/60">
          <Search className="h-5 w-5 text-brand-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="Quét toàn bộ Corpus PostgreSQL bằng pg_trgm..."
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-mono"
          />

          {/* Quick Options */}
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => setIsRegex(!isRegex)}
              className={`rounded px-2 py-1 font-mono text-[10px] font-bold border transition ${
                isRegex
                  ? 'border-brand-500 bg-brand-950 text-brand-300'
                  : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
              title="Bật/Tắt Regular Expression"
            >
              .*
            </button>
            <button
              type="button"
              onClick={() => setCaseSensitive(!caseSensitive)}
              className={`rounded px-2 py-1 font-mono text-[10px] font-bold border transition ${
                caseSensitive
                  ? 'border-brand-500 bg-brand-950 text-brand-300'
                  : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
              title="Phân biệt chữ hoa/thường"
            >
              Aa
            </button>
          </div>

          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results Area */}
        <div className="max-h-[60vh] overflow-y-auto p-3 space-y-2">
          {loading && (
            <div className="py-6 text-center text-xs text-slate-400 animate-pulse">
              Đang thực thi stored procedure verbatim_grep trên PostgreSQL...
            </div>
          )}

          {errorMsg && (
            <div className="rounded-lg bg-rose-950/80 p-3 text-xs text-rose-300 border border-rose-800">
              Lỗi cú pháp Regex / Grep: {errorMsg}
            </div>
          )}

          {!loading && !errorMsg && pattern.trim() && results.length === 0 && (
            <div className="py-8 text-center text-xs text-slate-400">
              Không tìm thấy chunk nào khớp với mẫu tìm kiếm.
            </div>
          )}

          {results.map((hit, idx) => (
            <div
              key={idx}
              onClick={() => {
                onSelectHit(hit.path, hit.doc_slug || '');
                onClose();
              }}
              className="group flex flex-col gap-1 rounded-xl border border-slate-800 bg-slate-950/60 p-3 hover:border-brand-500/60 hover:bg-slate-900/90 cursor-pointer transition"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {hit.doc_slug && (
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono font-bold text-brand-400">
                      {hit.doc_slug}
                    </span>
                  )}
                  <span className="font-mono text-[11px] font-semibold text-brand-300 group-hover:text-brand-200">
                    {hit.path}
                  </span>
                </div>
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-mono font-bold text-slate-400 uppercase">
                  {hit.field_matched}
                </span>
              </div>

              <div className="font-mono text-xs text-slate-300 line-clamp-2 leading-relaxed bg-slate-950/40 p-2 rounded border border-slate-850">
                {hit.match_snippet || hit.verbatim_text.substring(0, 150)}
              </div>
            </div>
          ))}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 px-4 py-2.5 bg-slate-950/80 text-[11px] text-slate-400 font-mono">
          <span>
            {results.length} kết quả khớp (PostgreSQL pg_trgm)
          </span>
          <span>Bấm ESC để đóng</span>
        </div>
      </div>
    </div>
  );
};
