import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronUp,
  Loader2,
  Plus,
  Terminal,
} from 'lucide-react';
import { CorpusDocument, ProviderId, ProviderStatus } from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';
import { AutoGrowTextarea } from '../common/AutoGrowTextarea';

interface QuestionComposerProps {
  question: string;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  validationError: string | null;
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
  validationError,
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
  const instanceId = useId();
  const textareaId = `qa-question-input-${instanceId}`;
  const scopeFilterId = `qa-scope-filter-${instanceId}`;
  const errorId = `qa-question-error-${instanceId}`;

  const [scopeOpen, setScopeOpen] = useState(false);
  const [scopeFilter, setScopeFilter] = useState('');
  const [providerOpen, setProviderOpen] = useState(false);

  const scopePopoverRef = useRef<HTMLDivElement | null>(null);
  const scopeTriggerRef = useRef<HTMLButtonElement | null>(null);
  const providerPopoverRef = useRef<HTMLDivElement | null>(null);
  const providerTriggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (ev: MouseEvent) => {
      const target = ev.target as Node;
      if (
        scopePopoverRef.current &&
        !scopePopoverRef.current.contains(target)
      ) {
        setScopeOpen(false);
      }
      if (
        providerPopoverRef.current &&
        !providerPopoverRef.current.contains(target)
      ) {
        setProviderOpen(false);
      }
    };

    const handleKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') {
        if (providerOpen) {
          ev.stopPropagation();
          setProviderOpen(false);
          providerTriggerRef.current?.focus();
        } else if (scopeOpen) {
          ev.stopPropagation();
          setScopeOpen(false);
          scopeTriggerRef.current?.focus();
        }
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [scopeOpen, providerOpen]);

  const filteredDocs = useMemo(() => {
    const q = scopeFilter.trim().toLowerCase();
    if (!q) return documents;
    return documents.filter(
      (d) =>
        d.doc_slug.toLowerCase().includes(q) ||
        (d.title && d.title.toLowerCase().includes(q))
    );
  }, [documents, scopeFilter]);

  const currentProvider =
    providers.find((p) => p.id === provider) ?? providers[0];
  const hasText = question.trim().length > 0;

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (loading) return;
        onSubmit();
      }}
      className="w-full"
    >
      {/* Centered heading above the chat box in initial view */}
      {!dockedAtBottom ? (
        <div className="mb-5 text-center">
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">
            <label htmlFor={textareaId} className="cursor-pointer">
              {t('answer.title')}
            </label>
          </h1>
        </div>
      ) : (
        <label htmlFor={textareaId} className="sr-only">
          {t('answer.label')}
        </label>
      )}

      {/* Minimalist Rounded Chat Card */}
      <div className="bg-composer-surface rounded-[22px] border border-slate-800/90 px-4 pt-3.5 pb-2.5 shadow-[0_2px_16px_rgba(15,23,42,0.05)] transition-colors duration-150 ease-out focus-within:border-slate-700">
        <AutoGrowTextarea
          id={textareaId}
          name="question"
          autoComplete="off"
          data-testid="qa-question-input"
          value={question}
          onValueChange={onQuestionChange}
          onSubmit={() => {
            if (!loading) {
              onSubmit();
            }
          }}
          aria-invalid={validationError ? 'true' : undefined}
          aria-describedby={validationError ? errorId : undefined}
          placeholder={
            dockedAtBottom
              ? 'Nhập câu hỏi tiếp theo trên kho tài liệu…'
              : t('answer.placeholder')
          }
          className={`w-full bg-transparent px-1 py-0.5 text-[15px] leading-relaxed text-slate-100 placeholder-slate-400 focus:outline-none focus-visible:outline-none ${
            dockedAtBottom ? 'min-h-[2.25rem]' : 'min-h-[4rem]'
          }`}
        />

        {validationError && (
          <div
            id={errorId}
            role="alert"
            className="mt-2 flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/60 px-3 py-2 text-xs text-rose-200"
          >
            <AlertCircle
              className="h-4 w-4 shrink-0 text-rose-400"
              aria-hidden="true"
            />
            <span>{validationError}</span>
          </div>
        )}

        {/* Bottom inline toolbar inside the chat card: ONLY "+" and Model Name on the left, circular "→" on the right */}
        <div className="mt-2 flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1">
            {/* "+" Document Scope Filter Trigger */}
            <div ref={scopePopoverRef} className="relative">
              <button
                ref={scopeTriggerRef}
                type="button"
                data-testid="qa-scope-toggle"
                aria-label={`${t('answer.scope')}: ${
                  selectedSlugs.length > 0
                    ? `${selectedSlugs.length}/${documents.length}`
                    : t('answer.scope.all', { n: documents.length })
                }`}
                aria-expanded={scopeOpen}
                aria-haspopup="dialog"
                onClick={() => {
                  setProviderOpen(false);
                  setScopeOpen((v) => !v);
                }}
                className={`inline-flex h-8 min-w-8 items-center justify-center gap-1 rounded-full px-2 text-xs font-medium transition-colors duration-150 ease-out focus:outline-none ${
                  selectedSlugs.length > 0
                    ? 'bg-brand-950/80 text-brand-300 border border-brand-700/80'
                    : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'
                }`}
              >
                <Plus className="h-4 w-4 shrink-0" aria-hidden="true" />
                {selectedSlugs.length > 0 && (
                  <span className="tabular-nums pe-0.5 text-[11px]">
                    {selectedSlugs.length}/{documents.length}
                  </span>
                )}
              </button>

              {scopeOpen && (
                <div
                  role="dialog"
                  aria-label="Chọn phạm vi tài liệu tra cứu"
                  className={`bg-composer-surface absolute start-0 z-30 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-800 p-3 shadow-xl space-y-2.5 ${
                    dockedAtBottom ? 'bottom-full mb-2' : 'top-full mt-2'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <label
                      htmlFor={scopeFilterId}
                      className="font-semibold text-slate-200"
                    >
                      {t('answer.scope.filterLabel')}
                    </label>
                    {selectedSlugs.length > 0 && (
                      <button
                        type="button"
                        onClick={onClearSelectedSlugs}
                        className="rounded px-1.5 py-0.5 text-xs font-medium text-brand-400 hover:underline focus:outline-none"
                      >
                        Bỏ chọn ({selectedSlugs.length})
                      </button>
                    )}
                  </div>
                  <input
                    id={scopeFilterId}
                    name="scopeFilter"
                    type="text"
                    autoComplete="off"
                    value={scopeFilter}
                    onChange={(e) => setScopeFilter(e.target.value)}
                    placeholder={t('answer.scope.filterPlaceholder')}
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 px-2.5 py-1.5 text-base sm:text-xs text-slate-100 placeholder-slate-400 focus:border-slate-600 focus:outline-none"
                  />
                  <div className="max-h-56 overflow-y-auto overscroll-contain space-y-1 rounded-xl border border-slate-800/80 bg-slate-950 p-1.5">
                    {filteredDocs.length === 0 ? (
                      <div className="flex items-center justify-between gap-2 px-2 py-2 text-xs text-slate-400">
                        <span>
                          Không có tài liệu khớp “{scopeFilter}”.
                        </span>
                        <button
                          type="button"
                          onClick={() => setScopeFilter('')}
                          className="shrink-0 font-medium text-brand-400 hover:underline"
                        >
                          Xóa lọc
                        </button>
                      </div>
                    ) : (
                      filteredDocs.map((doc) => {
                        const active = selectedSlugs.includes(doc.doc_slug);
                        return (
                          <label
                            key={doc.doc_slug}
                            className="flex cursor-pointer items-start gap-2.5 rounded-lg px-2 py-1.5 text-xs text-slate-200 hover:bg-slate-900"
                          >
                            <input
                              type="checkbox"
                              name="selectedDocSlugs"
                              value={doc.doc_slug}
                              checked={active}
                              onChange={() => onToggleDocSlug(doc.doc_slug)}
                              className="mt-0.5 accent-brand-500"
                            />
                            <span className="min-w-0 flex-1 break-words">
                              <span className="block font-mono text-xs text-slate-100">
                                {doc.doc_slug}
                              </span>
                              {doc.title && (
                                <span className="block text-xs text-slate-400">
                                  {doc.title}
                                </span>
                              )}
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Clean Custom Model Selector Popover (NO native OS <select>, NO redundant "CLI Provider:" text) */}
            <div ref={providerPopoverRef} className="relative">
              <button
                ref={providerTriggerRef}
                type="button"
                data-testid="qa-provider-select"
                aria-expanded={providerOpen}
                aria-haspopup="listbox"
                onClick={() => {
                  setScopeOpen(false);
                  setProviderOpen((v) => !v);
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium text-slate-300 hover:bg-slate-900 hover:text-slate-100 transition-colors duration-150 ease-out focus:outline-none"
              >
                <span>{currentProvider?.label ?? provider}</span>
                <ChevronUp
                  className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-150 ${
                    providerOpen ? 'rotate-180' : ''
                  }`}
                  aria-hidden="true"
                />
              </button>

              {providerOpen && (
                <div
                  role="listbox"
                  aria-label={t('answer.provider')}
                  className={`bg-composer-surface absolute start-0 z-30 w-72 rounded-2xl border border-slate-800 p-1.5 shadow-xl ${
                    dockedAtBottom ? 'bottom-full mb-2' : 'top-full mt-2'
                  }`}
                >
                  <div className="space-y-0.5">
                    {providers.map((p) => {
                      const isSelected = p.id === provider;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          role="option"
                          aria-selected={isSelected}
                          disabled={!p.available}
                          onClick={() => {
                            if (!p.available) return;
                            onProviderChange(p.id);
                            setProviderOpen(false);
                          }}
                          className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-start text-xs transition-colors duration-150 ${
                            !p.available
                              ? 'cursor-not-allowed text-slate-500 opacity-60'
                              : isSelected
                                ? 'bg-slate-900 font-semibold text-slate-100'
                                : 'font-medium text-slate-300 hover:bg-slate-900/70 hover:text-slate-100'
                          }`}
                        >
                          <span className="truncate">
                            {p.label} {!p.available ? '(chưa cài)' : ''}
                          </span>
                          {isSelected && (
                            <Check
                              className="h-3.5 w-3.5 shrink-0 text-brand-500"
                              aria-hidden="true"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {/* Agent MCP Mode Toggle neatly integrated inside the model menu */}
                  <div className="mt-1.5 border-t border-slate-800/80 pt-1.5">
                    <button
                      type="button"
                      data-testid="qa-mode-toggle"
                      disabled={!canUseAgentMode}
                      aria-pressed={effectiveAgentMode}
                      onClick={onToggleAgentMode}
                      className="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-start text-xs font-medium text-slate-300 hover:bg-slate-900/70 hover:text-slate-100 disabled:opacity-50"
                    >
                      <span className="inline-flex items-center gap-2">
                        <Terminal
                          className="h-3.5 w-3.5 shrink-0 text-slate-400"
                          aria-hidden="true"
                        />
                        <span>{t('answer.mode.agent')}</span>
                      </span>
                      <span
                        className={`inline-flex h-4 w-7 shrink-0 items-center rounded-full p-0.5 transition-colors duration-150 ${
                          effectiveAgentMode ? 'bg-brand-600' : 'bg-slate-700'
                        }`}
                      >
                        <span
                          className={`h-3 w-3 rounded-full bg-white transition-transform duration-150 ${
                            effectiveAgentMode ? 'translate-x-3' : 'translate-x-0'
                          }`}
                        />
                      </span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Circular Submit Button on the bottom-right */}
          <button
            type="submit"
            data-testid="qa-submit-btn"
            aria-disabled={loading}
            aria-label={loading ? t('answer.submitting') : t('answer.submit')}
            className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors duration-150 ease-out focus:outline-none ${
              hasText && !loading
                ? 'bg-slate-100 text-slate-950 hover:opacity-90'
                : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            {loading ? (
              <Loader2
                className="h-4 w-4 shrink-0 animate-spin"
                aria-hidden="true"
              />
            ) : (
              <ArrowRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </form>
  );
};
