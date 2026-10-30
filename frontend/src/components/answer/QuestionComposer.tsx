import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  Send,
  Terminal,
} from 'lucide-react';
import { CorpusDocument, ProviderId, ProviderStatus } from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';
import { AutoGrowTextarea } from '../common/AutoGrowTextarea';

interface QuestionComposerProps {
  question: string;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  providers: ProviderStatus[];
  provider: ProviderId;
  onProviderChange: (provider: ProviderId) => void;
  canUseAgentMode: boolean;
  effectiveAgentMode: boolean;
  onToggleAgentMode: () => void;
  documents: CorpusDocument[];
  selectedSlugs: string[];
  onToggleDocSlug: (slug: string) => void;
  onClearSelectedSlugs: () => void;
  dockedAtBottom: boolean;
}

export const QuestionComposer: React.FC<QuestionComposerProps> = ({
  question,
  onQuestionChange,
  onSubmit,
  loading,
  providers,
  provider,
  onProviderChange,
  canUseAgentMode,
  effectiveAgentMode,
  onToggleAgentMode,
  documents,
  selectedSlugs,
  onToggleDocSlug,
  onClearSelectedSlugs,
  dockedAtBottom,
}) => {
  const { t } = useI18n();
  const [scopeOpen, setScopeOpen] = useState(false);
  const [scopeFilter, setScopeFilter] = useState('');
  const scopePopoverRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (ev: MouseEvent) => {
      if (
        scopePopoverRef.current &&
        !scopePopoverRef.current.contains(ev.target as Node)
      ) {
        setScopeOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredDocs = useMemo(() => {
    const q = scopeFilter.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter(
      (d) =>
        d.doc_slug.toLowerCase().includes(q) ||
        (d.title && d.title.toLowerCase().includes(q))
    );
  }, [documents, scopeFilter]);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="rounded-2xl border border-slate-800 bg-slate-900/80 p-3.5 shadow-lg transition-all duration-300 focus-within:border-brand-500 space-y-3"
    >
      <AutoGrowTextarea
        data-testid="qa-question-input"
        value={question}
        onValueChange={onQuestionChange}
        onSubmit={onSubmit}
        placeholder={
          dockedAtBottom
            ? 'Hỏi câu tiếp theo trên kho tài liệu...'
            : t('answer.placeholder')
        }
        className="w-full bg-transparent px-1 py-1 text-base leading-snug text-slate-100 placeholder-slate-500 focus:outline-none"
      />

      <div className="flex flex-wrap items-center justify-between gap-2.5 border-t border-slate-800/80 pt-2.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* CLI Provider Pill */}
          <select
            data-testid="qa-provider-select"
            value={provider}
            onChange={(e) => onProviderChange(e.target.value as ProviderId)}
            aria-label={t('answer.provider')}
            className="rounded-lg border border-slate-700/90 bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-slate-200 focus:border-brand-500 focus:outline-none"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id} disabled={!p.available}>
                {p.label} {!p.available ? '(chưa cài)' : ''}
              </option>
            ))}
          </select>

          {/* Execution Mode Toggle Pill */}
          <button
            type="button"
            data-testid="qa-mode-toggle"
            disabled={!canUseAgentMode}
            onClick={onToggleAgentMode}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
              effectiveAgentMode
                ? 'border-brand-600/90 bg-brand-950/60 text-brand-300'
                : 'border-slate-700 bg-slate-950 text-slate-300'
            }`}
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>
              {effectiveAgentMode ? t('answer.mode.agent') : t('answer.mode.compose')}
            </span>
          </button>

          {/* Document Scope Popover Pill (opens upward when docked at bottom) */}
          {documents.length > 0 && (
            <div ref={scopePopoverRef} className="relative">
              <button
                type="button"
                data-testid="qa-scope-toggle"
                onClick={() => setScopeOpen((v) => !v)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                  selectedSlugs.length > 0
                    ? 'border-brand-600/80 bg-brand-950/50 text-brand-300'
                    : 'border-slate-700/90 bg-slate-950 text-slate-300 hover:border-slate-600'
                }`}
              >
                <FileText className="h-3.5 w-3.5 text-slate-400" />
                <span>
                  {t('answer.scope')}:{' '}
                  {selectedSlugs.length > 0
                    ? `${selectedSlugs.length}/${documents.length}`
                    : `Tất cả ${documents.length}`}
                </span>
                {dockedAtBottom ? (
                  <ChevronUp className="h-3.5 w-3.5 text-slate-400" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                )}
              </button>

              {scopeOpen && (
                <div
                  className={`absolute left-0 z-30 w-80 rounded-xl border border-slate-700 bg-slate-900 p-3 shadow-2xl space-y-2 ${
                    dockedAtBottom ? 'bottom-full mb-2' : 'top-full mt-1.5'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-200">
                      Giới hạn tài liệu tra cứu
                    </span>
                    {selectedSlugs.length > 0 && (
                      <button
                        type="button"
                        onClick={onClearSelectedSlugs}
                        className="text-[11px] font-medium text-brand-400 hover:underline"
                      >
                        Bỏ lọc ({selectedSlugs.length})
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    value={scopeFilter}
                    onChange={(e) => setScopeFilter(e.target.value)}
                    placeholder="Tìm nhanh doc_slug hoặc tiêu đề..."
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
                  />
                  <div className="max-h-52 overflow-y-auto space-y-1 rounded-lg border border-slate-800 bg-slate-950 p-1.5">
                    {filteredDocs.map((doc) => {
                      const active = selectedSlugs.includes(doc.doc_slug);
                      return (
                        <label
                          key={doc.doc_slug}
                          className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs text-slate-300 hover:bg-slate-900"
                        >
                          <input
                            type="checkbox"
                            checked={active}
                            onChange={() => onToggleDocSlug(doc.doc_slug)}
                            className="accent-brand-500"
                          />
                          <span
                            className="truncate font-mono text-[11px]"
                            title={doc.title}
                          >
                            {doc.doc_slug}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <button
          type="submit"
          data-testid="qa-submit-btn"
          disabled={loading || !question.trim()}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50 transition"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{t('answer.submitting')}</span>
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span>{t('answer.submit')}</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
};
