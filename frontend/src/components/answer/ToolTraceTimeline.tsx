import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Code2,
  Loader2,
  Terminal,
} from 'lucide-react';
import { StructuredToolOutput } from './StructuredToolOutput';
import { summarizeResultBadge, ToolTraceItem } from './toolTraceUtils';

interface ToolTraceTimelineProps {
  loading: boolean;
  providerLabel: string;
  toolTraces: ToolTraceItem[];
  onOpenExplorer: (docSlug: string, path: string) => void;
}

export const ToolTraceTimeline: React.FC<ToolTraceTimelineProps> = ({
  loading,
  providerLabel,
  toolTraces,
  onOpenExplorer,
}) => {
  // Default collapsed so the user sees a single sliding tool ticker line while running
  const [tracePanelOpen, setTracePanelOpen] = useState(false);
  const [collapsedSlideIdx, setCollapsedSlideIdx] = useState<number>(0);
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({});
  const [rawJsonMode, setRawJsonMode] = useState<Record<string, boolean>>({});

  // Automatically slide the collapsed single-tool ticker to the latest/running tool as N tools execute
  useEffect(() => {
    if (toolTraces.length > 0) {
      const runningIdx = toolTraces.findIndex((item) => item.status === 'running');
      setCollapsedSlideIdx(runningIdx >= 0 ? runningIdx : toolTraces.length - 1);
    } else {
      setCollapsedSlideIdx(0);
      setExpandedTraces({});
      setRawJsonMode({});
      setTracePanelOpen(false);
    }
  }, [toolTraces]);

  const totalToolElapsedMs = useMemo(
    () =>
      Math.round(
        toolTraces.reduce((acc, item) => acc + (item.elapsedMs ?? 0), 0) * 10
      ) / 10,
    [toolTraces]
  );

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

  const safeSlideIdx =
    toolTraces.length > 0
      ? Math.min(Math.max(0, collapsedSlideIdx), toolTraces.length - 1)
      : 0;
  const activeCollapsedTrace = toolTraces[safeSlideIdx] ?? null;
  const activeBadge = activeCollapsedTrace
    ? summarizeResultBadge(activeCollapsedTrace.tool, activeCollapsedTrace.result)
    : null;

  return (
    <div
      data-testid="qa-live-feed"
      className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden transition-all"
    >
      {!tracePanelOpen ? (
        /* COLLAPSED MODE: Shows ONLY ONE tool at a time (sliding through 1..N) */
        <div className="flex items-center justify-between gap-3 px-3.5 py-2.5">
          <button
            type="button"
            onClick={() => setTracePanelOpen(true)}
            className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
          >
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />

            {activeCollapsedTrace ? (
              <div
                key={activeCollapsedTrace.id}
                data-testid={`qa-tool-trace-${activeCollapsedTrace.tool}`}
                className="flex min-w-0 flex-1 items-center gap-2 transition-all duration-200"
              >
                {activeCollapsedTrace.status === 'running' && (
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-400" />
                )}
                {activeCollapsedTrace.status === 'done' && (
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                )}
                {activeCollapsedTrace.status === 'error' && (
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                )}

                <span className="shrink-0 rounded bg-slate-800/90 px-1.5 py-0.5 font-mono text-[10px] font-medium text-slate-300">
                  Bước {safeSlideIdx + 1}/{toolTraces.length}
                </span>

                <span className="shrink-0 rounded bg-slate-950 px-2 py-0.5 font-mono text-xs font-semibold text-brand-300 border border-slate-800">
                  {activeCollapsedTrace.tool}
                </span>

                {activeCollapsedTrace.argsSummary && (
                  <span className="truncate font-mono text-xs text-slate-300">
                    {activeCollapsedTrace.argsSummary}
                  </span>
                )}

                {activeBadge && (
                  <span className="hidden sm:inline-flex shrink-0 rounded bg-slate-950 px-2 py-0.5 font-mono text-[10px] text-emerald-300 border border-slate-800">
                    {activeBadge}
                  </span>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-400" />
                <span>Đang điều tra kho tài liệu qua {providerLabel}...</span>
              </div>
            )}
          </button>

          {/* Right Controls: Slide Stepper (when N > 1) + Elapsed + Expand Button */}
          <div className="flex shrink-0 items-center gap-2">
            {toolTraces.length > 1 && (
              <div className="inline-flex items-center rounded-lg border border-slate-800 bg-slate-950 p-0.5">
                <button
                  type="button"
                  onClick={() => setCollapsedSlideIdx((idx) => Math.max(0, idx - 1))}
                  disabled={safeSlideIdx <= 0}
                  title="Tool trước"
                  className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30"
                >
                  <ChevronLeft className="h-3 w-3" />
                </button>
                <span className="px-1.5 font-mono text-[10px] text-slate-400">
                  {safeSlideIdx + 1}/{toolTraces.length}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setCollapsedSlideIdx((idx) =>
                      Math.min(toolTraces.length - 1, idx + 1)
                    )
                  }
                  disabled={safeSlideIdx >= toolTraces.length - 1}
                  title="Tool tiếp theo"
                  className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30"
                >
                  <ChevronRight className="h-3 w-3" />
                </button>
              </div>
            )}

            {activeCollapsedTrace?.status === 'running' ? (
              <span className="font-mono text-[11px] text-brand-400">đang chạy...</span>
            ) : (
              totalToolElapsedMs > 0 && (
                <span className="font-mono text-[11px] text-slate-400">
                  {totalToolElapsedMs}ms
                </span>
              )
            )}

            <button
              type="button"
              onClick={() => setTracePanelOpen(true)}
              className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-[11px] font-medium text-slate-300 hover:border-brand-500 hover:text-brand-300 transition"
            >
              Mở rộng ({toolTraces.length}) ▾
            </button>
          </div>
        </div>
      ) : (
        /* EXPANDED MODE: Full Timeline Accordion with Structured Output Blocks */
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 bg-slate-900/90 px-4 py-2.5">
            <button
              type="button"
              onClick={() => setTracePanelOpen(false)}
              className="flex items-center gap-2 text-left text-xs font-semibold text-slate-200 hover:text-white"
            >
              <ChevronDown className="h-4 w-4 text-slate-400" />
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-400" />
              ) : (
                <Terminal className="h-3.5 w-3.5 text-brand-400" />
              )}
              <span>Tiến trình tra cứu công cụ MCP</span>
              <span className="rounded-full bg-slate-800 px-2 py-0.5 font-mono text-[11px] font-medium text-slate-300">
                {toolTraces.length} bước
              </span>
              {totalToolElapsedMs > 0 && (
                <span className="font-mono text-[11px] font-normal text-slate-400">
                  · {totalToolElapsedMs}ms
                </span>
              )}
            </button>

            <div className="flex items-center gap-2">
              {toolTraces.length > 0 && (
                <button
                  type="button"
                  onClick={toggleAllSteps}
                  className="rounded border border-slate-700/80 bg-slate-950 px-2 py-1 text-[11px] font-medium text-slate-300 hover:border-slate-600 hover:text-white transition"
                >
                  {anyStepExpanded ? 'Thu gọn các bước' : 'Bung hết chi tiết'}
                </button>
              )}
              <button
                type="button"
                onClick={() => setTracePanelOpen(false)}
                className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-[11px] font-medium text-slate-400 hover:text-slate-200"
              >
                Thu gọn ▴
              </button>
            </div>
          </div>

          <div className="p-3.5 space-y-2">
            {toolTraces.length === 0 ? (
              <div className="flex items-center gap-2 py-2 px-1 text-xs text-slate-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-400" />
                <span>
                  Agent đang phân tích câu hỏi và khởi tạo lệnh gọi công cụ MCP đầu tiên...
                </span>
              </div>
            ) : (
              toolTraces.map((item, stepIdx) => {
                const isExpanded = Boolean(expandedTraces[item.id]);
                const showRaw = Boolean(rawJsonMode[item.id]);
                const resultBadge = summarizeResultBadge(item.tool, item.result);
                const argEntries = item.args
                  ? Object.entries(item.args).filter(
                      ([, v]) => v !== null && v !== undefined && v !== '' && v !== false
                    )
                  : [];

                return (
                  <div
                    key={item.id}
                    data-testid={`qa-tool-trace-${item.tool}`}
                    className="rounded-lg border border-slate-800 bg-slate-950/90 transition hover:border-slate-700/90"
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
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
                    >
                      <div className="flex min-w-0 flex-1 items-center gap-2">
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                        )}
                        <span className="font-mono text-[10px] text-slate-500">
                          {stepIdx + 1}.
                        </span>
                        {item.status === 'running' && (
                          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-brand-400" />
                        )}
                        {item.status === 'done' && (
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                        )}
                        {item.status === 'error' && (
                          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
                        )}
                        <span className="shrink-0 rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-100 border border-slate-800">
                          {item.tool}
                        </span>
                        {item.argsSummary && (
                          <span className="truncate font-mono text-[11px] text-slate-400">
                            {item.argsSummary}
                          </span>
                        )}
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        {resultBadge && (
                          <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-[10px] font-medium text-brand-300 border border-slate-800">
                            {resultBadge}
                          </span>
                        )}
                        {item.status === 'running' ? (
                          <span className="font-mono text-[11px] text-brand-400">
                            đang chạy...
                          </span>
                        ) : (
                          item.elapsedMs !== undefined && (
                            <span className="font-mono text-[11px] text-slate-400">
                              {item.elapsedMs}ms
                            </span>
                          )
                        )}
                      </div>
                    </button>

                    {isExpanded && (
                      <div
                        data-testid={`qa-tool-trace-details-${item.tool}`}
                        className="border-t border-slate-800/80 px-3.5 py-3 space-y-3 bg-slate-900/20"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mr-1">
                              Tham số:
                            </span>
                            {argEntries.length === 0 ? (
                              <span className="font-mono text-[11px] text-slate-500">
                                (mặc định)
                              </span>
                            ) : (
                              argEntries.map(([k, v]) => (
                                <span
                                  key={k}
                                  className="inline-flex items-center gap-1 rounded border border-slate-800 bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-slate-300"
                                >
                                  <span className="text-slate-400">{k}:</span>
                                  <span className="text-slate-100">
                                    {typeof v === 'string'
                                      ? v.length > 70
                                        ? `"${v.slice(0, 70)}..."`
                                        : `"${v}"`
                                      : JSON.stringify(v)}
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
                            className={`inline-flex shrink-0 items-center gap-1 rounded border px-2 py-0.5 font-mono text-[10px] font-medium transition ${
                              showRaw
                                ? 'border-brand-500 bg-brand-950 text-brand-300'
                                : 'border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <Code2 className="h-3 w-3" />
                            <span>{showRaw ? 'Xem dạng Block' : 'Raw JSON'}</span>
                          </button>
                        </div>

                        {item.status === 'running' ? (
                          <div className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-400">
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-400" />
                            <span>Đang thực thi công cụ và chờ kết quả trả về...</span>
                          </div>
                        ) : item.error ? (
                          <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-words rounded border border-rose-900/80 bg-rose-950/40 p-2.5 font-mono text-[11px] leading-relaxed text-rose-300">
                            {item.error}
                          </pre>
                        ) : showRaw ? (
                          <div className="space-y-2">
                            <div>
                              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                Input JSON
                              </div>
                              <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[11px] text-slate-200">
                                {JSON.stringify(item.args ?? {}, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                Output JSON
                              </div>
                              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[11px] text-slate-200">
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
        </>
      )}
    </div>
  );
};
