import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { api } from '../../services/api';
import {
  CorpusDocument,
  SearchProvision,
  SearchResponse,
} from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';

interface DryRunSearchSimulatorProps {
  activeDocSlug?: string;
  onOpenInExplorer?: (docSlug: string, path: string) => void;
}

interface FlatProvisionItem {
  docSlug: string;
  docTitle: string;
  context: string;
  provision: SearchProvision;
}

export const DryRunSearchSimulator: React.FC<DryRunSearchSimulatorProps> = ({
  onOpenInExplorer,
}) => {
  const { t } = useI18n();
  const [query, setQuery] = useState('generateStaticParams dynamicParams');
  const [pattern, setPattern] = useState('generateStaticParams');
  const [pathPrefix, setPathPrefix] = useState('');
  const [limit, setLimit] = useState(10);
  const [isRegex, setIsRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [orderByReadingOrder, setOrderByReadingOrder] = useState(false);
  const [rerank, setRerank] = useState(false);
  const [selectedSlugs, setSelectedSlugs] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  const [documents, setDocuments] = useState<CorpusDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  useEffect(() => {
    api
      .getDocuments()
      .then(setDocuments)
      .catch(() => setDocuments([]));
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const cleanQuery = query.trim();
    if (!cleanQuery || loading) return;
    const effectivePattern = pattern.trim() || cleanQuery;

    setLoading(true);
    setError(null);
    try {
      const res = await api.search({
        query: cleanQuery,
        pattern: effectivePattern,
        limit,
        rerank,
        doc_slugs: selectedSlugs.length > 0 ? selectedSlugs : undefined,
        path_prefix: pathPrefix.trim() || undefined,
        is_regex: isRegex,
        case_sensitive: caseSensitive,
        order_by_reading_order: orderByReadingOrder,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void handleSearch();
  }, []);

  const flatItems = useMemo<FlatProvisionItem[]>(() => {
    if (!result) return [];
    const items: FlatProvisionItem[] = [];
    for (const grp of result.groups) {
      const docMeta = result.documents[grp.doc_slug];
      const docTitle = docMeta?.title || grp.doc_slug;
      for (const prov of grp.provisions) {
        items.push({
          docSlug: grp.doc_slug,
          docTitle,
          context: grp.context,
          provision: prov,
        });
      }
    }
    if (!orderByReadingOrder) {
      items.sort((a, b) => a.provision.rank - b.provision.rank);
    }
    return items;
  }, [result, orderByReadingOrder]);

  const toggleSlug = (slug: string) => {
    setSelectedSlugs((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const foundInBadge = (foundIn: SearchProvision['found_in']) => {
    if (foundIn === 'both') {
      return (
        <span className="rounded bg-emerald-950 px-2 py-0.5 text-[11px] font-medium text-emerald-300 border border-emerald-800">
          {t('search.found.both')}
        </span>
      );
    }
    if (foundIn === 'semantic_only') {
      return (
        <span className="rounded bg-sky-950 px-2 py-0.5 text-[11px] font-medium text-sky-300 border border-sky-800">
          {t('search.found.semantic_only')}
        </span>
      );
    }
    return (
      <span className="rounded bg-amber-950 px-2 py-0.5 text-[11px] font-medium text-amber-300 border border-amber-800">
        {t('search.found.verbatim_only')}
      </span>
    );
  };

  return (
    <div className="mx-auto h-full max-w-4xl overflow-y-auto px-5 py-6 sm:px-8 space-y-5">
      <div>
        <h1 className="text-base font-semibold text-slate-100">{t('search.title')}</h1>
        <p className="mt-1 text-xs text-slate-400">{t('search.subtitle')}</p>
      </div>

      <form onSubmit={handleSearch} className="space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              data-testid="search-query-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('search.query.placeholder')}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 py-2 pl-10 pr-3.5 text-sm text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
            />
          </div>
          <button
            type="button"
            data-testid="search-filters-toggle"
            onClick={() => setShowFilters((v) => !v)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition ${
              showFilters
                ? 'border-brand-500 bg-brand-950/60 text-brand-300'
                : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-600'
            }`}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t('search.filters.toggle')}</span>
            {showFilters ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            type="submit"
            data-testid="search-submit-btn"
            disabled={loading || !query.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50 transition"
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{t('search.searching')}</span>
              </>
            ) : (
              <span>{t('search.submit')}</span>
            )}
          </button>
        </div>

        {showFilters && (
          <div
            data-testid="search-filters-panel"
            className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  {t('search.pattern.label')}
                </label>
                <input
                  type="text"
                  data-testid="search-pattern-input"
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  placeholder={t('search.pattern.placeholder')}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  {t('search.limit.label')}
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value) || 10)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                {t('search.pathPrefix.label')}
              </label>
              <input
                type="text"
                value={pathPrefix}
                onChange={(e) => setPathPrefix(e.target.value)}
                placeholder="e.g. doc_slug.section_1"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>

            <div className="flex flex-wrap gap-4 pt-1 text-xs text-slate-300">
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isRegex}
                  onChange={(e) => setIsRegex(e.target.checked)}
                  className="rounded border-slate-700"
                />
                <span>{t('search.flag.regex')}</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={caseSensitive}
                  onChange={(e) => setCaseSensitive(e.target.checked)}
                  className="rounded border-slate-700"
                />
                <span>{t('search.flag.case')}</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={orderByReadingOrder}
                  onChange={(e) => setOrderByReadingOrder(e.target.checked)}
                  className="rounded border-slate-700"
                />
                <span>{t('search.flag.order')}</span>
              </label>
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rerank}
                  onChange={(e) => setRerank(e.target.checked)}
                  className="rounded border-slate-700"
                />
                <span>{t('search.flag.rerank')}</span>
              </label>
            </div>

            {documents.length > 0 && (
              <div className="pt-1">
                <div className="flex items-center justify-between text-[11px] font-medium text-slate-400 mb-1.5">
                  <span>
                    Giới hạn theo tài liệu (doc_slugs){' '}
                    {selectedSlugs.length > 0 ? `(${selectedSlugs.length}/${documents.length})` : `(Tất cả ${documents.length})`}:
                  </span>
                  {selectedSlugs.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedSlugs([])}
                      className="text-brand-400 hover:underline"
                    >
                      Bỏ chọn tất cả
                    </button>
                  )}
                </div>
                <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-2 flex flex-wrap gap-1.5">
                  {documents.map((doc) => {
                    const active = selectedSlugs.includes(doc.doc_slug);
                    return (
                      <button
                        key={doc.doc_slug}
                        type="button"
                        onClick={() => toggleSlug(doc.doc_slug)}
                        className={`rounded-md border px-2 py-0.5 font-mono text-[11px] transition ${
                          active
                            ? 'border-brand-500 bg-brand-950 text-brand-300'
                            : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {doc.doc_slug} ({doc.chunk_count})
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </form>

      {error && (
        <div className="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-200">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
            <div>
              Tìm thấy <strong className="text-slate-100">{flatItems.length}</strong> đoạn văn bản
              (verbatim_total={result.verbatim_total}, confidence={result.confidence})
            </div>
            <span className="font-mono">{result.elapsed_ms}ms</span>
          </div>

          <div data-testid="search-results-list" className="space-y-2.5">
            {flatItems.map((item) => (
              <div
                key={`${item.provision.rank}-${item.provision.path}`}
                data-testid={`search-result-row-${item.provision.rank}`}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-2.5 hover:border-slate-700 transition"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 min-w-0">
                    <span className="inline-flex items-center rounded bg-slate-800 px-2 py-0.5 font-mono text-xs font-semibold text-slate-200">
                      #{item.provision.rank}
                    </span>
                    {foundInBadge(item.provision.found_in)}
                    <span className="truncate font-mono text-xs font-medium text-brand-300">
                      {item.provision.path}
                    </span>
                    <span className="font-mono text-[11px] text-slate-400">
                      L{item.provision.start_line}–{item.provision.end_line}
                    </span>
                  </div>

                  {onOpenInExplorer && (
                    <button
                      type="button"
                      onClick={() => onOpenInExplorer(item.docSlug, item.provision.path)}
                      className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-200 hover:border-brand-500 hover:text-brand-300 transition"
                    >
                      <span>{t('search.openExplorer')}</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </button>
                  )}
                </div>

                {item.context && (
                  <div className="text-[11px] text-slate-400">
                    <span className="font-semibold text-slate-300">{item.docTitle}</span> —{' '}
                    {item.context}
                  </div>
                )}

                <pre className="whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
                  {item.provision.text}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
