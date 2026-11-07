import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Loader2,
} from 'lucide-react';
import { StructuredToolOutput } from './StructuredToolOutput';
import { summarizeResultBadge, ToolTraceItem } from './toolTraceUtils';

interface ToolTraceTimelineProps {
  loading: boolean;
  providerLabel: string;
  toolTraces: ToolTraceItem[];
  onOpenExplorer: (docSlug: string, path: string) => void;
}

function formatArgValue(v: unknown): string {
  if (typeof v === 'string') {
    return v.length > 56 ? `"${v.slice(0, 56)}…"` : `"${v}"`;
  }
  if (Array.isArray(v)) {
    if (v.length === 0) return '[]';
    const items = v.map((item) => String(item));
    if (items.length <= 2) {
      return items.join(', ');
    }
    return `${items[0]}, +${items.length - 1}`;
  }
  return JSON.stringify(v);
}

export const ToolTraceTimeline: React.FC<ToolTraceTimelineProps> = ({
  loading,
  providerLabel,
  toolTraces,
  onOpenExplorer,
}) => {
  const [tracePanelOpen, setTracePanelOpen] = useState(false);
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>(
    {}
  );
  const [rawJsonMode, setRawJsonMode] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (toolTraces.length === 0) {
      setExpandedTraces({});
      setRawJsonMode({});
      setTracePanelOpen(false);
    }
  }, [toolTraces.length]);

  const anyStepExpanded = useMemo(
    () => toolTraces.some((tItem) => Boolean(expandedTraces[tItem.id])),
    [toolTraces, expandedTraces]
  );

  const toggleAllSteps = () => {
    if (anyStepExpanded) {
      setExpandedTraces({});
    } else {
      const next: Record<string, boolean> = {};
      for (const item of toolTraces) {
        next[item.id] = true;
      }
      setExpandedTraces(next);
    }
  };

  if (!loading && toolTraces.length === 0) {
    return null;
  }

  const runningTrace =
    toolTraces.find((item) => item.status === 'running') ??
    toolTraces[toolTraces.length - 1] ??
    null;

  return (
    <div data-testid="qa-live-feed" className="space-y-2">
      {/* Minimalist borderless trigger line */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setTracePanelOpen((v) => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-100 transition-colors duration-150 focus:outline-none"
        >
          {loading ? (
            <>
              <Loader2
                className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-500"
                aria-hidden="true"
              />
              <span>
                {runningTrace
                  ? `Đang thực hiện bước ${toolTraces.length} (${runningTrace.tool})…`
                  : `Đang xử lý qua ${providerLabel}…`}
              </span>
            </>
          ) : (
            <span>Đã thực hiện {toolTraces.length} bước xử lý</span>
          )}
          {tracePanelOpen ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
        </button>

        {tracePanelOpen && toolTraces.length > 0 && (
          <button
            type="button"
            onClick={toggleAllSteps}
            className="text-xs font-medium text-slate-400 hover:text-slate-100 underline-offset-2 hover:underline focus:outline-none"
          >
            {anyStepExpanded ? 'Thu gọn chi tiết' : 'Bung hết chi tiết'}
          </button>
        )}
      </div>

      {/* Expanded Step List along a subtle vertical guide line */}
      {tracePanelOpen && (
        <div className="ms-1.5 border-s border-slate-800 ps-3.5 space-y-2">
          {toolTraces.length === 0 ? (
            <div className="py-1 text-xs text-slate-400">
              Đang khởi tạo lệnh gọi công cụ MCP đầu tiên…
            </div>
          ) : (
            toolTraces.map((item, stepIdx) => {
              const isExpanded = Boolean(expandedTraces[item.id]);
              const showRaw = Boolean(rawJsonMode[item.id]);
              const resultBadge = summarizeResultBadge(item.tool, item.result);
              const argEntries = item.args
                ? Object.entries(item.args).filter(
                    ([, v]) =>
                      v !== null && v !== undefined && v !== '' && v !== false
                  )
                : [];

              return (
                <div
                  key={item.id}
                  data-testid={`qa-tool-trace-${item.tool}`}
                  className="space-y-1.5"
                >
                  <button
                    type="button"
                    data-testid={`qa-tool-trace-toggle-${item.tool}`}
                    onClick={() =>
                      setExpandedTraces((prev) => ({
                        ...prev,
                        [item.id]: !prev[item.id],
                      }))
                    }
                    className="flex w-full items-center justify-between gap-2 rounded-lg py-1 text-start text-xs text-slate-300 hover:text-slate-50 transition-colors duration-150 focus:outline-none"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                      )}
                      <span className="font-mono text-xs text-slate-400 tabular-nums">
                        {stepIdx + 1}.
                      </span>
                      {item.status === 'running' && (
                        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-500" />
                      )}
                      {item.status === 'done' && (
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                      )}
                      {item.status === 'error' && (
                        <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
                      )}
                      <span className="shrink-0 rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs font-medium text-slate-100">
                        {item.tool}
                      </span>
                      {item.argsSummary && (
                        <span className="truncate font-mono text-xs text-slate-400">
                          {item.argsSummary}
                        </span>
                      )}
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      {resultBadge && (
                        <span className="font-mono text-xs text-brand-400">
                          {resultBadge}
                        </span>
                      )}
                      {item.elapsedMs !== undefined && (
                        <span className="font-mono text-xs text-slate-400 tabular-nums">
                          {item.elapsedMs}ms
                        </span>
                      )}
                    </div>
                  </button>

                  {isExpanded && (
                    <div
                      data-testid={`qa-tool-trace-details-${item.tool}`}
                      className="bg-composer-surface rounded-2xl border border-slate-800/80 p-3.5 space-y-3 overflow-hidden"
                    >
                      <div className="flex items-start justify-between gap-3 border-b border-slate-800/70 pb-2.5">
                        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                          {argEntries.length === 0 ? (
                            <span className="font-mono text-xs text-slate-400">
                              Tham số mặc định
                            </span>
                          ) : (
                            argEntries.map(([k, v]) => (
                              <span
                                key={k}
                                className="inline-flex max-w-full items-center gap-1 rounded-md bg-slate-900 px-2 py-0.5 font-mono text-xs text-slate-300"
                              >
                                <span className="shrink-0 text-slate-400">
                                  {k}:
                                </span>
                                <span className="truncate text-slate-100">
                                  {formatArgValue(v)}
                                </span>
                              </span>
                            ))
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            setRawJsonMode((prev) => ({
                              ...prev,
                              [item.id]: !prev[item.id],
                            }))
                          }
                          className={`inline-flex shrink-0 items-center gap-1 rounded-lg border px-2 py-1 font-mono text-xs font-medium transition-colors duration-150 ease-out focus:outline-none ${
                            showRaw
                              ? 'border-brand-500 bg-brand-950 text-brand-300'
                              : 'border-slate-800 bg-slate-900 text-slate-300 hover:text-slate-50'
                          }`}
                        >
                          <Code2 className="h-3 w-3" aria-hidden="true" />
                          <span>{showRaw ? 'Dạng rút gọn' : 'JSON'}</span>
                        </button>
                      </div>

                      {item.status === 'running' ? (
                        <div className="flex items-center gap-2 py-2 text-xs text-slate-400">
                          <Loader2
                            className="h-3.5 w-3.5 animate-spin text-brand-500"
                            aria-hidden="true"
                          />
                          <span>
                            Đang thực thi công cụ và chờ kết quả trả về…
                          </span>
                        </div>
                      ) : item.error ? (
                        <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-rose-950/40 p-3 font-mono text-xs leading-relaxed text-rose-300">
                          {item.error}
                        </pre>
                      ) : showRaw ? (
                        <div className="space-y-2.5">
                          <div>
                            <div className="mb-1 text-xs font-medium text-slate-400">
                              Tham số đầu vào (JSON)
                            </div>
                            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-2.5 font-mono text-xs text-slate-200">
                              {JSON.stringify(item.args ?? {}, null, 2)}
                            </pre>
                          </div>
                          <div>
                            <div className="mb-1 text-xs font-medium text-slate-400">
                              Kết quả trả về (JSON)
                            </div>
                            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-2.5 font-mono text-xs text-slate-200">
                              {JSON.stringify(item.result ?? {}, null, 2)}
                            </pre>
                          </div>
                        </div>
                      ) : (
                        <StructuredToolOutput
                          item={item}
                          onOpenExplorer={onOpenExplorer}
                        />
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
