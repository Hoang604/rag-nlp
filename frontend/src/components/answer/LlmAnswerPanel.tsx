import React, { useEffect, useRef, useState } from 'react';
import { ChevronRight, Radio, User } from 'lucide-react';
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

interface LlmAnswerPanelProps {
  documents: CorpusDocument[];
  onOpenInExplorer: (docSlug: string, path: string) => void;
}

const DEFAULT_SAMPLE_QUESTIONS = [
  'Tóm tắt nội dung và cấu trúc chính của tài liệu đầu tiên trong kho dữ liệu?',
  'Các khái niệm hoặc quy tắc quan trọng nào được định nghĩa kèm ví dụ minh họa?',
];

export const LlmAnswerPanel: React.FC<LlmAnswerPanelProps> = ({
  documents,
  onOpenInExplorer,
}) => {
  const { t } = useI18n();
  const [question, setQuestion] = useState('');
  const [submittedQuestion, setSubmittedQuestion] = useState<string>('');
  const [providers, setProviders] = useState<ProviderStatus[]>([
    { id: 'agy', label: 'Antigravity (Gemini 3.8 Flash)', available: true },
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
  const [sampleQuestions, setSampleQuestions] = useState<string[]>(DEFAULT_SAMPLE_QUESTIONS);

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

    api
      .getEvalCases()
      .then((cases) => {
        const picked = cases
          .map((c) => c.question.trim())
          .filter(Boolean)
          .slice(0, 3);
        if (picked.length > 0) {
          setSampleQuestions(picked);
        }
      })
      .catch(() => {
        // Keep default sample questions
      });
  }, []);

  // Connect to /api/qa/ws for real-time webhook -> WebSocket events
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
            llm_ms: prev?.llm_ms || (typeof data.elapsed_ms === 'number' ? data.elapsed_ms : 0),
            total_ms: prev?.total_ms || (typeof data.elapsed_ms === 'number' ? data.elapsed_ms : 0),
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

  const canUseAgentMode = provider === 'agy' || provider === 'claude';
  const effectiveAgentMode = canUseAgentMode ? agentMode : false;

  // Whether the user has started a conversation (switches composer from centered hero to bottom dock)
  const hasConversation = Boolean(
    loading || response || error || toolTraces.length > 0 || submittedQuestion
  );

  const handleSubmit = async (customQuestion?: string) => {
    const q = (customQuestion ?? question).trim();
    if (!q || loading) return;

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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const toggleDocSlug = (slug: string) => {
    setSelectedSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const providerLabel =
    providers.find((p) => p.id === provider)?.label || provider;

  const composerElement = (dockedAtBottom: boolean) => (
    <QuestionComposer
      question={question}
      onQuestionChange={setQuestion}
      onSubmit={() => void handleSubmit()}
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

  // STATE 1: Idle Centered Hero (Before any message is sent, like ChatGPT initial screen)
  if (!hasConversation) {
    return (
      <div className="flex h-full w-full flex-col justify-center overflow-y-auto px-5 py-8 sm:px-8">
        <div className="mx-auto w-full max-w-4xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-slate-100">
                {t('answer.title')}
              </h1>
              <p className="mt-1 text-xs text-slate-400">{t('answer.subtitle')}</p>
            </div>

            <span
              data-testid="qa-ws-status"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                wsConnected
                  ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-800'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              <Radio className="h-3 w-3" />
              {wsConnected ? t('answer.live.connected') : t('answer.live.disconnected')}
            </span>
          </div>

          {composerElement(false)}

          <div className="space-y-2">
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
              {t('answer.samples.title')} — bấm vào câu bất kỳ để chạy thử ngay:
            </div>
            <div className="space-y-2">
              {sampleQuestions.map((sq, idx) => (
                <button
                  key={idx}
                  type="button"
                  data-testid={`qa-sample-${idx}`}
                  onClick={() => void handleSubmit(sq)}
                  disabled={loading}
                  className="group flex w-full items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3 text-left text-sm text-slate-200 hover:border-brand-500/60 hover:bg-slate-900 transition"
                >
                  <span>{sq}</span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-slate-500 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-400" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // STATE 2: Active Conversation with Scrollable Feed + Bottom-Docked Composer Bar (like ChatGPT)
  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Top Scrollable Conversation Area */}
      <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-8">
        <div className="mx-auto max-w-5xl space-y-5 pb-4">
          {/* Compact Top Status Bar */}
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-slate-400">
              {t('answer.title')}
            </span>
            <span
              data-testid="qa-ws-status"
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                wsConnected
                  ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-800'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              <Radio className="h-3 w-3" />
              {wsConnected ? t('answer.live.connected') : t('answer.live.disconnected')}
            </span>
          </div>

          {/* User Question Bubble */}
          {(submittedQuestion || response?.question) && (
            <div className="flex justify-end">
              <div className="inline-flex max-w-3xl items-start gap-2.5 rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-sm leading-relaxed text-slate-100 shadow-sm">
                <User className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
                <span>{submittedQuestion || response?.question}</span>
              </div>
            </div>
          )}

          {/* MCP Tool Progress: Single-Tool Sliding Ticker when Collapsed, Full Structured Timeline when Expanded */}
          <ToolTraceTimeline
            loading={loading}
            providerLabel={providerLabel}
            toolTraces={toolTraces}
            onOpenExplorer={onOpenInExplorer}
          />

          {error && (
            <div
              data-testid="qa-error-banner"
              className="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-200"
            >
              {error}
            </div>
          )}

          {/* Grounded Answer & Validated Citations */}
          {response && (
            <GroundedAnswerSection
              response={response}
              onOpenExplorer={onOpenInExplorer}
            />
          )}
        </div>
      </div>

      {/* Bottom-Docked Composer Bar (ChatGPT Style) */}
      <div className="shrink-0 border-t border-slate-800/80 bg-slate-950/95 px-5 py-3.5 sm:px-8">
        <div className="mx-auto max-w-5xl">{composerElement(true)}</div>
      </div>
    </div>
  );
};
