import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowUpLeft,
  BookOpen,
  Building2,
  Car,
  FileCheck,
  Flame,
  HeartHandshake,
  Landmark,
  Radio,
  RotateCcw,
  Scale,
  ShieldAlert,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { api } from '../../services/api';
import {
  AnswerCitation,
  AnswerResponse,
  CorpusDocument,
  ProviderId,
  ProviderStatus,
  QAWebhookEvent,
} from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';
import { GroundedAnswerSection } from './GroundedAnswerSection';
import { QuestionComposer } from './QuestionComposer';
import { ToolTraceTimeline } from './ToolTraceTimeline';
import { summarizeArgs, ToolTraceItem } from './toolTraceUtils';
import {
  BAOHIEM_DEMO_QUESTIONS,
  DemoScenarioQuestion,
} from './baohiemDemoQuestions';

interface LlmAnswerPanelProps {
  documents: CorpusDocument[];
  onOpenInExplorer: (docSlug: string, path: string) => void;
}

const SCENARIO_ICONS = [
  Landmark,
  HeartHandshake,
  Scale,
  Flame,
  ShieldAlert,
  FileCheck,
  Building2,
  Car,
  TrendingUp,
  Wallet,
] as const;

function readInitialScenarioFromUrl(): DemoScenarioQuestion | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  const scenarioId = params.get('scenario');
  if (!scenarioId) return null;
  return BAOHIEM_DEMO_QUESTIONS.find((q) => q.id === scenarioId) ?? null;
}

function syncScenarioToUrl(scenarioId: string | null): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  if (scenarioId) {
    url.searchParams.set('scenario', scenarioId);
  } else {
    url.searchParams.delete('scenario');
  }
  window.history.replaceState({}, '', url.toString());
}

export const LlmAnswerPanel: React.FC<LlmAnswerPanelProps> = ({
  documents,
  onOpenInExplorer,
}) => {
  const { t } = useI18n();
  const initialScenario = useMemo(() => readInitialScenarioFromUrl(), []);

  const [question, setQuestion] = useState<string>(
    initialScenario?.question ?? ''
  );
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(
    initialScenario?.id ?? null
  );
  const [submittedQuestion, setSubmittedQuestion] = useState<string>('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([
    { id: 'agy', label: 'Antigravity (Gemini 3.8 Flash)', available: true },
    {
      id: 'agy-argon',
      label: 'Antigravity (Gemini 4 Argon Medium)',
      available: true,
    },
    { id: 'claude', label: 'Claude Code', available: true },
    { id: 'codex', label: 'Codex', available: false },
  ]);
  const [provider, setProvider] = useState<ProviderId>('agy');
  const [agentMode, setAgentMode] = useState<boolean>(true);
  const [selectedSlugs, setSelectedSlugs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AnswerResponse | null>(null);

  const [wsConnected, setWsConnected] = useState(false);
  const [toolTraces, setToolTraces] = useState<ToolTraceItem[]>([]);

  const activeSessionRef = useRef<string | null>(null);
  const questionRef = useRef<string>(submittedQuestion || question);
  const providerRef = useRef<ProviderId>(provider);

  useEffect(() => {
    questionRef.current = submittedQuestion || question;
  }, [submittedQuestion, question]);

  useEffect(() => {
    providerRef.current = provider;
  }, [provider]);

  useEffect(() => {
    if (!question.trim()) return;
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [question]);

  useEffect(() => {
    api
      .getAnswerProviders()
      .then((list) => {
        if (list.length > 0) {
          setProviders(list);
          const preferred =
            list.find((p) => p.id === 'agy' && p.available) ??
            list.find((p) => p.available);
          if (preferred) setProvider(preferred.id);
        }
      })
      .catch(() => {
        // Keep default providers list
      });
  }, []);

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/api/qa/ws`;
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        if (!closed) {
          setTimeout(connect, 2000);
        }
      };
      ws.onerror = () => setWsConnected(false);
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as QAWebhookEvent;
          handleWsEvent(data);
        } catch {
          // Ignore malformed message
        }
      };
    };

    const handleWsEvent = (data: QAWebhookEvent) => {
      if (data.event === 'qa_started' && data.session_id) {
        activeSessionRef.current = data.session_id;
        setToolTraces([]);
        if (typeof data.question === 'string' && data.question.trim()) {
          setSubmittedQuestion(data.question.trim());
        }
        return;
      }

      if (data.session_id && !activeSessionRef.current) {
        activeSessionRef.current = data.session_id;
      }

      if (data.event === 'tool_start' && data.tool) {
        const traceId = `${data.tool}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        setToolTraces((prev) => [
          ...prev,
          {
            id: traceId,
            tool: data.tool || 'tool',
            argsSummary: summarizeArgs(data.args),
            args: data.args,
            status: 'running',
            timestamp: data.timestamp || new Date().toISOString(),
          },
        ]);
      } else if (data.event === 'tool_done' && data.tool) {
        setToolTraces((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].tool === data.tool && copy[i].status === 'running') {
              copy[i] = {
                ...copy[i],
                status: 'done',
                args: data.args ?? copy[i].args,
                result: data.result,
                elapsedMs: data.elapsed_ms,
              };
              return copy;
            }
          }
          return [
            ...copy,
            {
              id: `${data.tool}-${Date.now()}`,
              tool: data.tool || 'tool',
              argsSummary: summarizeArgs(data.args),
              args: data.args,
              result: data.result,
              status: 'done',
              elapsedMs: data.elapsed_ms,
              timestamp: data.timestamp || new Date().toISOString(),
            },
          ];
        });
      } else if (data.event === 'tool_error' && data.tool) {
        setToolTraces((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].tool === data.tool && copy[i].status === 'running') {
              copy[i] = {
                ...copy[i],
                status: 'error',
                args: data.args ?? copy[i].args,
                error: data.error,
                elapsedMs: data.elapsed_ms,
              };
              return copy;
            }
          }
          return [
            ...copy,
            {
              id: `${data.tool}-${Date.now()}`,
              tool: data.tool || 'tool',
              argsSummary: summarizeArgs(data.args),
              args: data.args,
              status: 'error',
              error: data.error,
              elapsedMs: data.elapsed_ms,
              timestamp: data.timestamp || new Date().toISOString(),
            },
          ];
        });
      } else if (data.event === 'answer_submitted' && data.payload) {
        const sub = data.payload as Record<string, unknown>;
        if (typeof sub.answer === 'string' && Array.isArray(sub.citations)) {
          setResponse((prev) => ({
            question: prev?.question || questionRef.current,
            provider: prev?.provider || providerRef.current,
            answer: sub.answer as string,
            abstained: Boolean(sub.abstained),
            citations: sub.citations as AnswerCitation[],
            retrieval_ms: prev?.retrieval_ms || 0,
            llm_ms:
              prev?.llm_ms ||
              (typeof data.elapsed_ms === 'number' ? data.elapsed_ms : 0),
            total_ms:
              prev?.total_ms ||
              (typeof data.elapsed_ms === 'number' ? data.elapsed_ms : 0),
          }));
        }
      } else if (data.event === 'qa_completed' && data.payload) {
        const completed = data.payload as unknown as AnswerResponse;
        if (completed && typeof completed.answer === 'string') {
          setResponse(completed);
        }
      }
    };

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const canUseAgentMode =
    provider === 'agy' || provider === 'agy-argon' || provider === 'claude';
  const effectiveAgentMode = canUseAgentMode ? agentMode : false;

  const hasConversation = Boolean(
    loading || response || error || toolTraces.length > 0 || submittedQuestion
  );

  const handleQuestionChange = (val: string) => {
    setQuestion(val);
    if (validationError && val.trim()) {
      setValidationError(null);
    }
    const matchedScenario = BAOHIEM_DEMO_QUESTIONS.find(
      (item) => item.question === val.trim()
    );
    const nextId = matchedScenario?.id ?? null;
    setActiveScenarioId(nextId);
    syncScenarioToUrl(nextId);
  };

  const handleSubmit = async (
    customQuestion?: string,
    scenarioId?: string | null
  ) => {
    if (loading) return;
    const q = (customQuestion ?? question).trim();
    if (!q) {
      setValidationError(t('answer.validation.empty'));
      const el = document.querySelector<HTMLTextAreaElement>(
        '[data-testid="qa-question-input"]'
      );
      el?.focus();
      return;
    }

    setValidationError(null);
    if (scenarioId !== undefined) {
      setActiveScenarioId(scenarioId);
      syncScenarioToUrl(scenarioId);
    }
    setSubmittedQuestion(q);
    setQuestion('');

    const sessionId = `qa-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    activeSessionRef.current = sessionId;
    setLoading(true);
    setError(null);
    setResponse(null);
    setToolTraces([]);

    try {
      const res = await api.askQuestion({
        question: q,
        provider,
        agent_mode: effectiveAgentMode,
        limit: 8,
        doc_slugs: selectedSlugs,
        session_id: sessionId,
      });
      setResponse(res);
    } catch (err) {
      setQuestion(q);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectScenario = (
    scenario: DemoScenarioQuestion,
    runImmediately: boolean
  ) => {
    setValidationError(null);
    setActiveScenarioId(scenario.id);
    syncScenarioToUrl(scenario.id);
    if (runImmediately) {
      void handleSubmit(scenario.question, scenario.id);
    } else {
      setQuestion(scenario.question);
      const el = document.querySelector<HTMLTextAreaElement>(
        '[data-testid="qa-question-input"]'
      );
      el?.focus();
    }
  };

  const handleReturnToScenarioList = () => {
    if (loading) return;
    setSubmittedQuestion('');
    setResponse(null);
    setError(null);
    setToolTraces([]);
  };

  const toggleDocSlug = (slug: string) => {
    setSelectedSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const providerLabel =
    providers.find((p) => p.id === provider)?.label || provider;

  const liveStatusText = useMemo(() => {
    if (loading) {
      return `Đang xử lý câu hỏi qua ${providerLabel} (${toolTraces.length} lượt gọi công cụ MCP).`;
    }
    if (error) {
      return `Truy vấn gặp lỗi: ${error}`;
    }
    if (response) {
      return `Đã hoàn tất câu trả lời với ${response.citations.length} nguồn trích dẫn đã xác thực.`;
    }
    return '';
  }, [loading, error, response, providerLabel, toolTraces.length]);

  const composerElement = (dockedAtBottom: boolean) => (
    <QuestionComposer
      question={question}
      onQuestionChange={handleQuestionChange}
      onSubmit={() => void handleSubmit()}
      validationError={validationError}
      loading={loading}
      providers={providers}
      provider={provider}
      onProviderChange={setProvider}
      canUseAgentMode={canUseAgentMode}
      effectiveAgentMode={effectiveAgentMode}
      onToggleAgentMode={() => setAgentMode((v) => !v)}
      documents={documents}
      selectedSlugs={selectedSlugs}
      onToggleDocSlug={toggleDocSlug}
      onClearSelectedSlugs={() => setSelectedSlugs([])}
      dockedAtBottom={dockedAtBottom}
    />
  );

  // STATE 1: Minimalist Centered Chat Box + Single-Line Vertical List of 10 Insurance Scenarios
  if (!hasConversation) {
    return (
      <div className="flex h-full w-full flex-col overflow-y-auto px-4 py-8 sm:px-6">
        <div role="status" aria-live="polite" className="sr-only">
          {liveStatusText}
        </div>

        <div className="my-auto mx-auto w-full max-w-[42rem] py-6">
          {composerElement(false)}

          {/* Clean Single-Line List of 10 Suggested Scenarios directly beneath Composer */}
          <section
            aria-label={t('answer.scenarios.heading')}
            data-testid="qa-scenarios-list"
            className="mt-3.5 space-y-0.5 px-2"
          >
            {BAOHIEM_DEMO_QUESTIONS.map((item, idx) => {
              const Icon = SCENARIO_ICONS[idx % SCENARIO_ICONS.length];
              const isSelected = activeScenarioId === item.id;

              return (
                <div
                  key={item.id}
                  data-testid={`qa-sample-card-${item.id}`}
                  className={`group flex items-center justify-between gap-2 rounded-xl px-2.5 py-1.5 transition-colors duration-150 ease-out ${
                    isSelected
                      ? 'bg-slate-900/90 text-slate-100'
                      : 'hover:bg-slate-900/60'
                  }`}
                >
                  <button
                    type="button"
                    data-testid={`qa-sample-${idx}`}
                    aria-disabled={loading}
                    onClick={() => handleSelectScenario(item, true)}
                    className="flex min-w-0 flex-1 items-center gap-3 text-start text-[13px] leading-normal text-slate-300 group-hover:text-slate-100 focus:outline-none"
                  >
                    <Icon
                      className="h-4 w-4 shrink-0 text-slate-400 group-hover:text-slate-200 transition-colors duration-150"
                      aria-hidden="true"
                    />
                    <span className="truncate">{item.title}</span>
                  </button>

                  <button
                    type="button"
                    data-testid={`qa-sample-fill-${idx}`}
                    aria-label={`${t('answer.scenarios.fillInput')}: ${item.title}`}
                    title={t('answer.scenarios.fillInput')}
                    onClick={() => handleSelectScenario(item, false)}
                    className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-slate-400 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:bg-slate-800 hover:text-slate-100 transition-opacity duration-150 ease-out focus:outline-none"
                  >
                    <ArrowUpLeft className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
              );
            })}
          </section>
        </div>
      </div>
    );
  }

  // STATE 2: Active Conversation with Centered Thread + Bottom-Docked Minimalist Composer
  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div role="status" aria-live="polite" className="sr-only">
        {liveStatusText}
      </div>

      {/* Top Scrollable Conversation Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-5 pb-8">
          {/* Compact Top Status Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              data-testid="qa-return-scenarios-btn"
              aria-disabled={loading}
              onClick={handleReturnToScenarioList}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-slate-800 bg-composer-surface px-3 py-1 text-xs font-medium text-slate-200 hover:border-slate-600 aria-disabled:opacity-50 transition-colors duration-150 ease-out focus:outline-none"
            >
              <BookOpen
                className="h-3.5 w-3.5 shrink-0 text-brand-400"
                aria-hidden="true"
              />
              <span>{t('answer.scenarios.backToList')}</span>
            </button>

            <span
              data-testid="qa-ws-status"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${
                wsConnected
                  ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-800'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              <Radio className="h-3 w-3 shrink-0" aria-hidden="true" />
              <span>
                {wsConnected
                  ? t('answer.live.connected')
                  : t('answer.live.disconnected')}
              </span>
            </span>
          </div>

          {/* User Question Pill (borderless, clean like reference) */}
          {(submittedQuestion || response?.question) && (
            <div className="flex justify-end">
              <div className="max-w-xl rounded-2xl bg-slate-900/90 px-4 py-2.5 text-sm leading-relaxed text-slate-100 whitespace-pre-line text-start">
                {submittedQuestion || response?.question}
              </div>
            </div>
          )}

          {/* Assistant Turn: Borderless Tool Trace + Markdown Answer */}
          <div className="space-y-2.5">
            <ToolTraceTimeline
              loading={loading}
              providerLabel={providerLabel}
              toolTraces={toolTraces}
              onOpenExplorer={onOpenInExplorer}
            />

            {error && (
              <div
                role="alert"
                data-testid="qa-error-banner"
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-200"
              >
                <span className="min-w-0 flex-1 leading-relaxed">{error}</span>
                <button
                  type="button"
                  data-testid="qa-retry-btn"
                  onClick={() =>
                    void handleSubmit(
                      submittedQuestion || question,
                      activeScenarioId
                    )
                  }
                  className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg border border-rose-700 bg-rose-900/60 px-3 py-1.5 text-xs font-semibold text-rose-100 hover:bg-rose-900 transition-colors duration-150 ease-out focus:outline-none"
                >
                  <RotateCcw className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>{t('answer.retry')}</span>
                </button>
              </div>
            )}

            {response && (
              <GroundedAnswerSection
                response={response}
                onOpenExplorer={onOpenInExplorer}
              />
            )}
          </div>
        </div>
      </div>

      {/* Bottom-Docked Composer Bar */}
      <div className="shrink-0 bg-slate-950/95 px-4 pb-4 pt-2 sm:px-6">
        <div className="mx-auto max-w-3xl">{composerElement(true)}</div>
      </div>
    </div>
  );
};
