import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUpRight, ChevronDown, ChevronRight } from 'lucide-react';
import { AnswerCitation, AnswerResponse } from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';

function preprocessCitationsForMarkdown(text: string): string {
  return text.replace(/\[#(\d+)\](?!\()/g, '[#$1](#cite-$1)');
}

const SourceRow: React.FC<{
  citation: AnswerCitation;
  highlighted: boolean;
  onOpenExplorer: (docSlug: string, path: string) => void;
}> = ({ citation, highlighted, onOpenExplorer }) => {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<boolean>(false);

  return (
    <div
      id={`citation-row-${citation.index}`}
      data-testid={`citation-row-${citation.index}`}
      className={`rounded-xl border transition-colors duration-150 ${
        highlighted
          ? 'border-brand-500 bg-slate-900/60'
          : 'border-slate-800/80 bg-composer-surface hover:border-slate-700'
      }`}
    >
      <div className="flex items-center justify-between gap-2 px-3.5 py-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-start text-slate-200 hover:text-slate-50 focus:outline-none"
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          )}
          <span className="inline-flex items-center rounded bg-brand-950 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-brand-300 border border-brand-800">
            #{citation.index}
          </span>
          <span className="truncate font-mono text-xs font-medium text-slate-200">
            {citation.path}
          </span>
          <span className="shrink-0 font-mono text-[11px] text-slate-400 tabular-nums">
            L{citation.start_line}–{citation.end_line}
          </span>
        </button>

        <button
          type="button"
          data-testid={`citation-open-explorer-${citation.index}`}
          onClick={() => onOpenExplorer(citation.doc_slug, citation.path)}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-[11px] font-medium text-slate-300 hover:border-slate-700 hover:text-slate-50 transition-colors duration-150 focus:outline-none"
        >
          <span>{t('answer.citations.openExplorer')}</span>
          <ArrowUpRight className="h-3 w-3" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-800/80 px-3.5 py-3 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>
              {citation.doc_title} (
              <code className="font-mono">{citation.doc_slug}</code>)
            </span>
          </div>
          <pre className="whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
            {citation.verbatim_text}
          </pre>
          {citation.contextualized_text &&
            citation.contextualized_text !== citation.verbatim_text && (
              <details className="text-xs text-slate-400">
                <summary className="cursor-pointer select-none font-medium hover:text-slate-100">
                  {t('answer.citations.context')}
                </summary>
                <pre className="mt-1.5 whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950/60 p-2.5 font-mono text-[11px] text-slate-300">
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
  const [highlightedCitation, setHighlightedCitation] = useState<number | null>(
    null
  );
  const [citationsOpen, setCitationsOpen] = useState<boolean>(false);

  const sortedCitations = useMemo(
    () =>
      response.citations
        ? [...response.citations].sort((a, b) => a.index - b.index)
        : [],
    [response]
  );

  const markdownContent = useMemo(
    () => preprocessCitationsForMarkdown(response.answer),
    [response.answer]
  );

  const handleSelectCitation = (index: number) => {
    setHighlightedCitation(index);
    setCitationsOpen(true);
    setTimeout(() => {
      const el = document.getElementById(`citation-row-${index}`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 50);
  };

  return (
    <div data-testid="qa-answer-card" className="space-y-5">
      {response.abstained && (
        <div className="inline-flex items-center rounded-lg bg-amber-950 px-2.5 py-1 text-xs font-medium text-amber-300 border border-amber-800">
          {t('answer.result.abstained')}
        </div>
      )}

      {/* Borderless Markdown Answer Body directly on the canvas */}
      <div
        data-testid="qa-answer-text"
        className="text-[15px] leading-[1.7] text-slate-100 space-y-3"
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h2 className="mt-5 mb-2 first:mt-0 text-base font-bold tracking-tight text-slate-50">
                {children}
              </h2>
            ),
            h2: ({ children }) => (
              <h3 className="mt-5 mb-2 first:mt-0 text-[15.5px] font-bold tracking-tight text-slate-50">
                {children}
              </h3>
            ),
            h3: ({ children }) => (
              <h4 className="mt-4 mb-1.5 first:mt-0 text-[15px] font-semibold text-slate-50">
                {children}
              </h4>
            ),
            h4: ({ children }) => (
              <h5 className="mt-3 mb-1 first:mt-0 text-[14.5px] font-semibold text-slate-100">
                {children}
              </h5>
            ),
            p: ({ children }) => (
              <p className="my-2.5 first:mt-0 leading-[1.7] text-slate-100">
                {children}
              </p>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-slate-50">
                {children}
              </strong>
            ),
            ul: ({ children }) => (
              <ul className="my-2.5 list-disc ps-5 space-y-2 marker:text-slate-400">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="my-2.5 list-decimal ps-5 space-y-2.5 marker:font-semibold marker:text-slate-100">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="ps-1 leading-[1.7] text-slate-100 [&>p]:my-1">
                {children}
              </li>
            ),
            hr: () => <hr className="my-4 border-slate-800/70" />,
            blockquote: ({ children }) => (
              <blockquote className="my-3 border-s-2 border-slate-700 ps-3.5 italic text-slate-300">
                {children}
              </blockquote>
            ),
            code: ({ className, children }) => {
              const isBlock = Boolean(className);
              if (isBlock) {
                return (
                  <pre className="my-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 p-3 font-mono text-xs leading-relaxed text-slate-200">
                    <code>{children}</code>
                  </pre>
                );
              }
              return (
                <code className="rounded-md border border-slate-800/80 bg-slate-900/90 px-1.5 py-0.5 font-mono text-[13px] font-medium text-slate-100">
                  {children}
                </code>
              );
            },
            table: ({ children }) => (
              <div className="my-3 overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full border-collapse text-start text-xs">
                  {children}
                </table>
              </div>
            ),
            th: ({ children }) => (
              <th className="border-b border-slate-800 bg-slate-900/80 px-3 py-2 text-start font-semibold text-slate-100">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border-b border-slate-800/60 px-3 py-2 text-slate-200">
                {children}
              </td>
            ),
            a: ({ href, children }) => {
              if (href?.startsWith('#cite-')) {
                const idx = parseInt(href.slice('#cite-'.length), 10);
                const isActive = highlightedCitation === idx;
                return (
                  <button
                    type="button"
                    onClick={() => handleSelectCitation(idx)}
                    className={`mx-0.5 inline-flex items-center rounded px-1.5 py-0.2 font-mono text-[11px] font-semibold align-baseline transition-colors duration-150 focus:outline-none ${
                      isActive
                        ? 'bg-brand-600 text-white'
                        : 'bg-brand-950/90 text-brand-300 border border-brand-800/80 hover:bg-brand-900'
                    }`}
                  >
                    #{idx}
                  </button>
                );
              }
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-brand-400 underline underline-offset-2 hover:text-brand-300"
                >
                  {children}
                </a>
              );
            },
          }}
        >
          {markdownContent}
        </ReactMarkdown>
      </div>

      {/* Collapsible Validated Citations Footer */}
      {sortedCitations.length > 0 && (
        <div className="pt-2 space-y-2 border-t border-slate-800/60">
          <button
            type="button"
            onClick={() => setCitationsOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-100 transition-colors duration-150 focus:outline-none"
          >
            <span>
              {t('answer.citations.title', { n: sortedCitations.length })}
            </span>
            {citationsOpen ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>

          {citationsOpen && (
            <div className="space-y-2 pt-1">
              {sortedCitations.map((c) => (
                <SourceRow
                  key={c.index}
                  citation={c}
                  highlighted={highlightedCitation === c.index}
                  onOpenExplorer={onOpenExplorer}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
