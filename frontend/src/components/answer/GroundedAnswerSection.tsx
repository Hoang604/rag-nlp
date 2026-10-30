import React, { useMemo, useState } from 'react';
import { ArrowUpRight, ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import { AnswerCitation, AnswerResponse } from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';

function renderAnswerWithCitations(
  text: string,
  activeIdx: number | null,
  onSelectCitation: (index: number) => void
): React.ReactNode {
  const parts = text.split(/(\[#\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[#(\d+)\]$/);
    if (!m) return <React.Fragment key={i}>{part}</React.Fragment>;
    const idx = parseInt(m[1], 10);
    const isActive = activeIdx === idx;
    return (
      <button
        key={i}
        type="button"
        onClick={() => onSelectCitation(idx)}
        className={`mx-0.5 inline-flex items-center rounded px-1.5 py-0.5 font-mono text-xs font-semibold transition ${
          isActive
            ? 'bg-brand-500 text-white'
            : 'bg-brand-950 text-brand-300 border border-brand-800 hover:bg-brand-900'
        }`}
      >
        #{idx}
      </button>
    );
  });
}

const SourceRow: React.FC<{
  citation: AnswerCitation;
  highlighted: boolean;
  onOpenExplorer: (docSlug: string, path: string) => void;
}> = ({ citation, highlighted, onOpenExplorer }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<boolean>(true);

  return (
    <div
      id={`citation-row-${citation.index}`}
      data-testid={`citation-row-${citation.index}`}
      className={`rounded-lg border transition-colors ${
        highlighted
          ? 'border-brand-500 bg-slate-900'
          : 'border-slate-800 bg-slate-900/50 hover:border-slate-700'
      }`}
    >
      <div className="flex items-center justify-between gap-2 px-3.5 py-2.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
          )}
          <span className="inline-flex items-center rounded bg-brand-950 px-1.5 py-0.5 font-mono text-xs font-semibold text-brand-300 border border-brand-800">
            #{citation.index}
          </span>
          <span className="truncate font-mono text-xs font-medium text-slate-200">
            {citation.path}
          </span>
          <span className="shrink-0 font-mono text-[11px] text-slate-400">
            L{citation.start_line}–{citation.end_line}
          </span>
        </button>

        <button
          type="button"
          data-testid={`citation-open-explorer-${citation.index}`}
          onClick={() => onOpenExplorer(citation.doc_slug, citation.path)}
          className="inline-flex shrink-0 items-center gap-1 rounded border border-slate-700 bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-200 hover:border-brand-500 hover:text-brand-300 transition"
        >
          <span>{t('answer.citations.openExplorer')}</span>
          <ArrowUpRight className="h-3 w-3" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-800/80 px-3.5 py-3 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>
              {citation.doc_title} (<code className="font-mono">{citation.doc_slug}</code>)
            </span>
          </div>
          <pre className="whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
            {citation.verbatim_text}
          </pre>
          {citation.contextualized_text &&
            citation.contextualized_text !== citation.verbatim_text && (
              <details className="text-xs text-slate-400">
                <summary className="cursor-pointer select-none font-medium hover:text-slate-200">
                  {t('answer.citations.context')}
                </summary>
                <pre className="mt-1.5 whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950/60 p-2.5 font-mono text-[11px] text-slate-300">
                  {citation.contextualized_text}
                </pre>
              </details>
            )}
        </div>
      )}
    </div>
  );
};

interface GroundedAnswerSectionProps {
  response: AnswerResponse;
  onOpenExplorer: (docSlug: string, path: string) => void;
}

export const GroundedAnswerSection: React.FC<GroundedAnswerSectionProps> = ({
  response,
  onOpenExplorer,
}) => {
  const { t } = useI18n();
  const [highlightedCitation, setHighlightedCitation] = useState<number | null>(null);

  const sortedCitations = useMemo(
    () =>
      response.citations ? [...response.citations].sort((a, b) => a.index - b.index) : [],
    [response]
  );

  const handleSelectCitation = (index: number) => {
    setHighlightedCitation(index);
    const el = document.getElementById(`citation-row-${index}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  return (
    <div data-testid="qa-answer-card" className="space-y-5">
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-400" />
            <h2 className="text-sm font-semibold text-slate-100">
              {t('answer.result.title')}
            </h2>
            {response.abstained && (
              <span className="rounded bg-amber-950 px-2 py-0.5 text-[11px] font-medium text-amber-300 border border-amber-800">
                {t('answer.result.abstained')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px] text-slate-400">
            <span>provider={response.provider}</span>
            <span>{response.total_ms}ms</span>
          </div>
        </div>

        <div
          data-testid="qa-answer-text"
          className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100"
        >
          {renderAnswerWithCitations(
            response.answer,
            highlightedCitation,
            handleSelectCitation
          )}
        </div>
      </div>

      {sortedCitations.length > 0 && (
        <div className="space-y-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {t('answer.citations.title', { n: sortedCitations.length })}
          </h3>
          <div className="space-y-2.5">
            {sortedCitations.map((c) => (
              <SourceRow
                key={c.index}
                citation={c}
                highlighted={highlightedCitation === c.index}
                onOpenExplorer={onOpenExplorer}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
