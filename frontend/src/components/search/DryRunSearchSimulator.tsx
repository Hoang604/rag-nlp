import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Filter,
  FileSearch,
  Loader2,
  Search,
  Zap,
} from 'lucide-react';
import { api } from '../../services/api';
import { CorpusDocument, SearchProvision, SearchResponse } from '../../types/api';

interface DryRunSearchSimulatorProps {
  activeDocSlug?: string;
}

const EXAMPLE_QUERIES = [
  'Cấu trúc và nguyên lý hoạt động của hệ thống',
  'Tham số cấu hình và yêu cầu tiên quyết',
  'Quy trình xử lý ngoại lệ và khôi phục lỗi',
  'Định dạng dữ liệu và giao thức tích hợp',
];

export const DryRunSearchSimulator: React.FC<DryRunSearchSimulatorProps> = () => {
  const [query, setQuery] = useState('');
  const [pattern, setPattern] = useState('');
  const [orderReadingOrder, setOrderReadingOrder] = useState(false);
  const [matchLimit, setMatchLimit] = useState(5);
  const [rerank, setRerank] = useState(true);
  const [pathPrefix, setPathPrefix] = useState('');
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<CorpusDocument[]>([]);
  const [scope, setScope] = useState<string[]>([]);
  const [scopeOpen, setScopeOpen] = useState(false);

  useEffect(() => {
    api
      .getDocuments()
      .then(setDocs)
      .catch(() => setDocs([]));
  }, []);

  const runSearch = useCallback(
    async (text: string, pat: string) => {
      const trimmedQuery = text.trim();
      const trimmedPattern = pat.trim() || trimmedQuery;
      if (!trimmedQuery) return;
      setLoading(true);
      setError(null);
      try {
        const response = await api.search({
          query: trimmedQuery,
          pattern: trimmedPattern,
          limit: matchLimit,
          rerank,
          doc_slugs: scope.length > 0 ? scope : undefined,
          path_prefix: pathPrefix.trim() || undefined,
          order_by_reading_order: orderReadingOrder,
        });
        setResult(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không gọi được API tìm kiếm.');
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    [matchLimit, rerank, scope, pathPrefix, orderReadingOrder]
  );

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void runSearch(query, pattern);
  };

  const pickExample = (example: string) => {
    setQuery(example);
    void runSearch(example, example);
  };

  const hits: SearchProvision[] = (result?.groups ?? []).flatMap((g) => g.provisions);

  const CONFIDENCE_NOTE: Record<string, { title: string; body: string; tone: string }> = {
    none: {
      title: 'Không có nội dung khớp từ khóa với câu hỏi',
      body: 'Câu hỏi này nhiều khả năng nằm ngoài phạm vi corpus. Các kết quả dưới đây chỉ là những đoạn gần nhất về mặt ngữ nghĩa vector.',
      tone: 'border-rose-900 bg-rose-950/40 text-rose-200',
    },
    low: {
      title: 'Độ tương đồng thấp',
      body: 'Không có mục nào thực sự gần với câu hỏi. Hãy đọc kỹ trước khi sử dụng — kết quả có thể không liên quan.',
      tone: 'border-amber-900 bg-amber-950/40 text-amber-200',
    },
  };
  const note = result && result.confidence ? CONFIDENCE_NOTE[result.confidence] : undefined;

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-slate-950 p-6">
      <div className="mb-6 rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-brand-500/30 bg-brand-600/20 text-brand-400">
            <Zap className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">Truy hồi trên kho tài liệu đã lưu trữ</h3>
            <p className="text-xs text-slate-400">
              Gọi thẳng <span className="font-mono text-brand-400">hybrid_search</span> — đường truy hồi MCP:
              dense vector + sparse tsvector, hợp nhất Reciprocal Rank Fusion (RRF) và Cross-Encoder Reranker.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Câu hỏi / ngữ cảnh ngữ nghĩa (dense vector + sparse FTS)..."
                className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2.5 pl-10 pr-4 text-xs font-medium text-slate-100 shadow-inner focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div className="relative flex-1">
              <input
                type="text"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                placeholder="Từ khóa neo cứng / regex pattern (mặc định lấy theo câu hỏi)..."
                className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2.5 px-4 text-xs font-medium text-slate-100 shadow-inner focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={pathPrefix}
              onChange={(e) => setPathPrefix(e.target.value)}
              placeholder="Tiền tố path..."
              title="Lọc theo tiền tố LTree path (ví dụ: sec_1)"
              className="w-28 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
            />

            <label
              title="Xếp hạng lại top kết quả bằng Cross-Encoder"
              className={`flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                rerank
                  ? 'border-emerald-500/50 bg-emerald-600/20 text-emerald-300'
                  : 'border-slate-700 bg-slate-950 text-slate-400 hover:text-slate-200'
              }`}
            >
              <input
                type="checkbox"
                checked={rerank}
                onChange={(e) => setRerank(e.target.checked)}
                className="h-3 w-3 accent-emerald-500"
              />
              <span>Rerank</span>
            </label>

            <label
              title="Sắp xếp kết quả verbatim theo thứ tự đọc trong tài liệu"
              className={`flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                orderReadingOrder
                  ? 'border-brand-500/50 bg-brand-600/20 text-brand-300'
                  : 'border-slate-700 bg-slate-950 text-slate-400 hover:text-slate-200'
              }`}
            >
              <input
                type="checkbox"
                checked={orderReadingOrder}
                onChange={(e) => setOrderReadingOrder(e.target.checked)}
                className="h-3 w-3 accent-brand-500"
              />
              <span>Thứ tự đọc</span>
            </label>

            <select
              value={matchLimit}
              onChange={(e) => setMatchLimit(Number(e.target.value))}
              className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-brand-500 focus:outline-none"
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
            </select>

            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="flex items-center gap-1.5 rounded-xl border border-brand-500/40 bg-brand-600/20 px-4 py-2 text-xs font-bold text-brand-300 transition hover:bg-brand-600/30 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              <span>Tra cứu</span>
            </button>
          </div>
        </form>

        <div className="mt-3 border-t border-slate-800 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setScopeOpen((open) => !open)}
              className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-[11px] font-medium text-slate-300 transition hover:border-brand-500 hover:text-brand-300"
            >
              <Filter className="h-3.5 w-3.5" />
              <span>
                {scope.length === 0
                  ? `Phạm vi: toàn bộ ${docs.length || ''} tài liệu`.trim()
                  : `Phạm vi: ${scope.length} tài liệu đã chọn`}
              </span>
            </button>
            {scope.length > 0 && (
              <button
                type="button"
                onClick={() => setScope([])}
                className="rounded-lg px-2 py-1 text-[11px] text-slate-400 transition hover:text-white"
              >
                Bỏ lọc
              </button>
            )}
          </div>

          {scopeOpen && (
            <div className="mt-2 grid gap-1 rounded-xl border border-slate-800 bg-slate-950/70 p-2 sm:grid-cols-2">
              {docs.map((doc) => (
                <label
                  key={doc.doc_slug}
                  className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1 text-[11px] text-slate-300 transition hover:bg-slate-900"
                >
                  <input
                    type="checkbox"
                    checked={scope.includes(doc.doc_slug)}
                    onChange={(e) =>
                      setScope((current) =>
                        e.target.checked
                          ? [...current, doc.doc_slug]
                          : current.filter((code) => code !== doc.doc_slug)
                      )
                    }
                    className="mt-0.5 h-3.5 w-3.5 accent-brand-500"
                  />
                  <span>
                    <span className="font-mono font-semibold text-slate-100">
                      {doc.doc_slug}
                    </span>
                    <span className="ml-1 text-slate-500">
                      {doc.chunk_count} mục
                    </span>
                    <span className="block truncate text-slate-500">{doc.title}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-medium text-slate-400">Câu hỏi gợi ý:</span>
          {EXAMPLE_QUERIES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => pickExample(example)}
              className="rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-[11px] text-slate-300 transition hover:border-brand-500 hover:text-brand-300"
            >
              {example}
            </button>
          ))}
        </div>

        {result && (
          <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-3 text-[11px] text-slate-400">
            <div>
              <span className="font-semibold uppercase tracking-wider text-slate-500 mr-2">Độ tin cậy:</span>
              <span className="font-mono font-bold text-slate-200 uppercase">{result.confidence}</span>
            </div>
            <div>
              <span className="font-semibold uppercase tracking-wider text-slate-500 mr-2">Độ trễ:</span>
              <span className="font-mono text-slate-200">{result.elapsed_ms} ms</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Kết quả ({hits.length} mục tìm thấy)
          </h4>
          {result && (
            <span className="font-mono text-[11px] text-slate-400">&ldquo;{result.query}&rdquo;</span>
          )}
        </div>

        {error ? (
          <div className="flex items-start gap-2 rounded-xl border border-rose-900 bg-rose-950/40 p-4 text-xs text-rose-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
            <div>
              <p className="font-semibold">Không tra cứu được</p>
              <p className="mt-1 text-rose-300/80">{error}</p>
            </div>
          </div>
        ) : loading ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center text-xs text-slate-400">
            <Loader2 className="mx-auto mb-2 h-8 w-8 animate-spin text-slate-500" />
            <p className="font-semibold text-slate-300">Đang truy hồi trên toàn corpus…</p>
          </div>
        ) : !result ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center text-xs text-slate-400">
            <FileSearch className="mx-auto mb-2 h-8 w-8 text-slate-500" />
            <p className="font-semibold text-slate-300">Nhập câu hỏi để tra cứu trên corpus</p>
            <p className="mt-1 text-[11px]">
              Hệ thống sử dụng pgvector cosine similarity kết hợp BM25 sparse rank và reranker.
            </p>
          </div>
        ) : hits.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center text-xs text-slate-400">
            Không có mục nào phù hợp với câu hỏi này.
          </div>
        ) : (
          <div className="space-y-3">
            {note && (
              <div
                className={`flex items-start gap-2 rounded-xl border p-4 text-xs ${note.tone}`}
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
                <div>
                  <p className="font-semibold">{note.title}</p>
                  <p className="mt-1 opacity-80">{note.body}</p>
                </div>
              </div>
            )}
            {hits.map((hit) => {
              const docSlug = hit.path.split('.')[0];
              const isTable = Boolean(hit.metadata?.is_table);
              const tableSummary = typeof hit.metadata?.table_summary === 'string' ? hit.metadata.table_summary : null;
              return (
                <div
                  key={hit.path}
                  className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow transition hover:border-slate-700"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-500/20 font-mono text-[11px] font-bold text-brand-300">
                        #{hit.rank}
                      </span>
                      <span className="rounded border border-slate-700 bg-slate-950 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-200">
                        {docSlug}
                      </span>
                      <span className="text-xs font-bold text-slate-100 font-mono">
                        {hit.path}
                      </span>
                      <span
                        className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${
                          hit.found_in === 'both'
                            ? 'border-emerald-800/80 bg-emerald-950/60 text-emerald-300'
                            : hit.found_in === 'semantic_only'
                            ? 'border-brand-800/80 bg-brand-950/60 text-brand-300'
                            : 'border-amber-800/80 bg-amber-950/60 text-amber-300'
                        }`}
                      >
                        {hit.found_in}
                      </span>
                      {isTable && (
                        <span
                          title={tableSummary ?? 'Đoạn này là một phần của bảng'}
                          className="rounded border border-violet-800/80 bg-violet-950/60 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
                        >
                          bảng
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="mb-2 whitespace-pre-wrap rounded-lg border border-slate-800/80 bg-slate-950/80 p-3 font-mono text-xs leading-relaxed text-slate-200">
                    {hit.text}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
