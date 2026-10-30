import React, { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  Loader2,
  Play,
  Plus,
  Save,
  Trash2,
  XCircle,
} from 'lucide-react';
import { api } from '../../services/api';
import { EvalCase, ExpectedTarget } from '../../types/api';
import { useI18n } from '../../i18n/I18nContext';

export const EvalPanel: React.FC = () => {
  const { t } = useI18n();
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [filterSet, setFilterSet] = useState<string>('');
  const [filterDomain, setFilterDomain] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'hit' | 'miss'>('all');

  const [loading, setLoading] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [runningSingle, setRunningSingle] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable form state for selected case
  const [draft, setDraft] = useState<EvalCase | null>(null);

  const fetchCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.getEvalCases();
      setCases(list);
      if (list.length > 0 && !selectedId) {
        setSelectedId(list[0].id);
        setDraft(structuredClone(list[0]));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchCases();
  }, []);

  useEffect(() => {
    const found = cases.find((c) => c.id === selectedId);
    if (found) {
      setDraft(structuredClone(found));
    }
  }, [selectedId, cases]);

  const testSets = useMemo(
    () => Array.from(new Set(cases.map((c) => c.test_set).filter(Boolean))),
    [cases]
  );
  const domains = useMemo(
    () => Array.from(new Set(cases.map((c) => c.domain).filter(Boolean))),
    [cases]
  );

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      if (filterSet && c.test_set !== filterSet) return false;
      if (filterDomain && c.domain !== filterDomain) return false;
      if (filterStatus === 'hit' && (c.rank == null || c.rank > 10)) return false;
      if (filterStatus === 'miss' && c.rank != null && c.rank <= 10) return false;
      return true;
    });
  }, [cases, filterSet, filterDomain, filterStatus]);

  const metrics = useMemo(() => {
    const evaluated = filteredCases.filter(
      (c) => c.rank != null || (c.top_hits && c.top_hits.length > 0) || c.elapsed_ms != null
    );
    const n = evaluated.length;
    if (n === 0) {
      return {
        total: filteredCases.length,
        evaluatedCount: 0,
        foundPct: '—',
        hit1Pct: '—',
        hit5Pct: '—',
        mrrPct: '—',
      };
    }
    let found = 0;
    let hit1 = 0;
    let hit5 = 0;
    let mrrSum = 0;
    for (const c of evaluated) {
      if (c.rank != null && c.rank >= 1 && c.rank <= 10) {
        found += 1;
        if (c.rank === 1) hit1 += 1;
        if (c.rank <= 5) hit5 += 1;
        mrrSum += 1 / c.rank;
      }
    }
    return {
      total: filteredCases.length,
      evaluatedCount: n,
      foundPct: `${((found / n) * 100).toFixed(1)}%`,
      hit1Pct: `${((hit1 / n) * 100).toFixed(1)}%`,
      hit5Pct: `${((hit5 / n) * 100).toFixed(1)}%`,
      mrrPct: `${((mrrSum / n) * 100).toFixed(1)}%`,
    };
  }, [filteredCases]);

  const handleRunAll = async () => {
    if (runningAll) return;
    setRunningAll(true);
    setError(null);
    try {
      const updated = await api.runAllEvalCases();
      setCases(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunningAll(false);
    }
  };

  const handleRunSingle = async () => {
    if (!draft || runningSingle) return;
    setRunningSingle(true);
    setError(null);
    try {
      await api.updateEvalCase(draft.id, {
        test_set: draft.test_set,
        domain: draft.domain,
        question: draft.question,
        query: draft.query,
        pattern: draft.pattern,
        expected: draft.expected,
        is_regex: draft.is_regex,
        case_sensitive: draft.case_sensitive,
        doc_slugs: draft.doc_slugs,
        path_prefix: draft.path_prefix,
        note: draft.note,
      });
      const updatedCase = await api.runEvalCase(draft.id);
      setCases((prev) => prev.map((c) => (c.id === updatedCase.id ? updatedCase : c)));
      setDraft(structuredClone(updatedCase));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunningSingle(false);
    }
  };

  const handleSave = async () => {
    if (!draft || saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.updateEvalCase(draft.id, {
        test_set: draft.test_set,
        domain: draft.domain,
        question: draft.question,
        query: draft.query,
        pattern: draft.pattern,
        expected: draft.expected,
        is_regex: draft.is_regex,
        case_sensitive: draft.case_sensitive,
        doc_slugs: draft.doc_slugs,
        path_prefix: draft.path_prefix,
        note: draft.note,
      });
      setCases((prev) => {
        const exists = prev.some((c) => c.id === saved.id);
        return exists ? prev.map((c) => (c.id === saved.id ? saved : c)) : [saved, ...prev];
      });
      setDraft(structuredClone(saved));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleAddCase = async () => {
    const newId = `custom_${Date.now().toString(36)}`;
    const defaultSlug = cases[0]?.expected[0]?.doc_slug || '';
    const newCase: EvalCase = {
      id: newId,
      test_set: filterSet || 'custom',
      domain: filterDomain || 'general',
      question: 'Câu hỏi kiểm thử mới',
      query: 'truy vấn ngữ nghĩa',
      pattern: 'từ khóa',
      expected: [{ doc_slug: defaultSlug, path_suffix: '' }],
      is_regex: false,
      case_sensitive: false,
      doc_slugs: [],
      path_prefix: null,
      note: '',
      top_hits: [],
    };
    setCases((prev) => [newCase, ...prev]);
    setSelectedId(newId);
    setDraft(structuredClone(newCase));
  };

  const handleDelete = async () => {
    if (!draft) return;
    try {
      await api.deleteEvalCase(draft.id);
      const next = cases.filter((c) => c.id !== draft.id);
      setCases(next);
      setSelectedId(next[0]?.id || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const updateExpected = (idx: number, field: keyof ExpectedTarget, val: string) => {
    if (!draft) return;
    const nextExp = draft.expected.map((item, i) =>
      i === idx ? { ...item, [field]: val } : item
    );
    setDraft({ ...draft, expected: nextExp });
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col overflow-hidden px-5 py-5 sm:px-8 gap-4">
      {/* Top Summary & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex flex-wrap items-center gap-4">
          <h1 className="text-base font-semibold text-slate-100">{t('eval.title')}</h1>
          <div
            data-testid="eval-metrics-bar"
            className="flex flex-wrap items-center gap-3 font-mono text-xs text-slate-300"
          >
            <span className="rounded bg-slate-900 px-2.5 py-1 border border-slate-800">
              Cases: <strong>{metrics.total}</strong>
            </span>
            <span className="rounded bg-emerald-950/60 px-2.5 py-1 text-emerald-300 border border-emerald-800">
              Found@10: <strong>{metrics.foundPct}</strong>
            </span>
            <span className="rounded bg-slate-900 px-2.5 py-1 border border-slate-800">
              H@1: <strong>{metrics.hit1Pct}</strong>
            </span>
            <span className="rounded bg-slate-900 px-2.5 py-1 border border-slate-800">
              H@5: <strong>{metrics.hit5Pct}</strong>
            </span>
            <span className="rounded bg-brand-950/60 px-2.5 py-1 text-brand-300 border border-brand-800">
              MRR@10: <strong>{metrics.mrrPct}</strong>
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filterSet}
            onChange={(e) => setFilterSet(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200"
          >
            <option value="">{t('eval.filter.allSets')}</option>
            {testSets.map((ts) => (
              <option key={ts} value={ts}>
                {ts}
              </option>
            ))}
          </select>

          <select
            value={filterDomain}
            onChange={(e) => setFilterDomain(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200"
          >
            <option value="">{t('eval.filter.allDomains')}</option>
            {domains.map((dm) => (
              <option key={dm} value={dm}>
                {dm}
              </option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as 'all' | 'hit' | 'miss')}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200"
          >
            <option value="all">{t('eval.filter.allStatus')}</option>
            <option value="hit">{t('eval.filter.hit')}</option>
            <option value="miss">{t('eval.filter.miss')}</option>
          </select>

          <button
            type="button"
            onClick={handleAddCase}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-slate-600"
          >
            {t('eval.addCase')}
          </button>

          <button
            type="button"
            data-testid="eval-run-all-btn"
            disabled={runningAll || loading}
            onClick={handleRunAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50"
          >
            {runningAll ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{t('eval.runningAll')}</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>{t('eval.runAll')}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-800 bg-rose-950/50 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {/* Main 2-column body */}
      <div className="grid flex-1 grid-cols-1 gap-5 overflow-hidden lg:grid-cols-12">
        {/* Left List of Eval Cases */}
        <div
          data-testid="eval-cases-list"
          className="overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/40 divide-y divide-slate-800/80 lg:col-span-5"
        >
          {filteredCases.map((c) => {
            const isSelected = c.id === selectedId;
            const hasRun =
              c.rank != null || (c.top_hits && c.top_hits.length > 0) || c.elapsed_ms != null;
            const isHit = c.rank != null && c.rank <= 10;
            return (
              <button
                key={c.id}
                type="button"
                data-testid={`eval-case-row-${c.id}`}
                onClick={() => setSelectedId(c.id)}
                className={`flex w-full items-start justify-between gap-2.5 px-3.5 py-2.5 text-left transition ${
                  isSelected ? 'bg-slate-800/90' : 'hover:bg-slate-900'
                }`}
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] font-semibold text-slate-400">
                      {c.id}
                    </span>
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                      {c.domain}
                    </span>
                    {c.found_in && (
                      <span className="font-mono text-[10px] text-brand-400">
                        {c.found_in}
                      </span>
                    )}
                  </div>
                  <p className="line-clamp-2 text-xs text-slate-200">{c.question}</p>
                </div>

                <div className="shrink-0 text-right">
                  {!hasRun ? (
                    <span className="inline-flex items-center rounded bg-slate-800/80 px-2 py-0.5 font-mono text-[11px] text-slate-400 border border-slate-700">
                      Chưa chạy
                    </span>
                  ) : isHit ? (
                    <span className="inline-flex items-center gap-1 rounded bg-emerald-950 px-2 py-0.5 font-mono text-xs font-semibold text-emerald-300 border border-emerald-800">
                      <CheckCircle2 className="h-3 w-3" />#{c.rank}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded bg-rose-950 px-2 py-0.5 font-mono text-xs font-semibold text-rose-300 border border-rose-800">
                      <XCircle className="h-3 w-3" />
                      Miss
                    </span>
                  )}
                  {c.elapsed_ms != null && (
                    <div className="mt-1 font-mono text-[10px] text-slate-500">
                      {c.elapsed_ms}ms
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Case Editor & Top Hits */}
        <div className="overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-4 lg:col-span-7">
          {draft ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-brand-300">
                    {draft.id}
                  </span>
                  <span className="text-xs text-slate-400">({draft.test_set})</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    data-testid="eval-run-single-btn"
                    disabled={runningSingle}
                    onClick={handleRunSingle}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50"
                  >
                    {runningSingle ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Play className="h-3.5 w-3.5" />
                    )}
                    <span>{t('eval.runSingle')}</span>
                  </button>
                  <button
                    type="button"
                    data-testid="eval-save-btn"
                    disabled={saving}
                    onClick={handleSave}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-slate-600"
                  >
                    <Save className="h-3.5 w-3.5" />
                    <span>{t('eval.save')}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="inline-flex items-center gap-1 rounded-lg border border-rose-900 bg-rose-950/50 px-2.5 py-1.5 text-xs text-rose-300 hover:bg-rose-900/50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>{t('eval.delete')}</span>
                  </button>
                </div>
              </div>

              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Bộ kiểm thử (test_set)
                    </label>
                    <input
                      type="text"
                      value={draft.test_set}
                      onChange={(e) => setDraft({ ...draft, test_set: e.target.value })}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Nhóm / Miền (domain)
                    </label>
                    <input
                      type="text"
                      value={draft.domain}
                      onChange={(e) => setDraft({ ...draft, domain: e.target.value })}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    Câu hỏi (question)
                  </label>
                  <input
                    type="text"
                    value={draft.question}
                    onChange={(e) => setDraft({ ...draft, question: e.target.value })}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-slate-100"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Truy vấn ngữ nghĩa (query)
                    </label>
                    <input
                      type="text"
                      value={draft.query}
                      onChange={(e) => setDraft({ ...draft, query: e.target.value })}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Từ khóa neo (pattern)
                    </label>
                    <input
                      type="text"
                      value={draft.pattern}
                      onChange={(e) => setDraft({ ...draft, pattern: e.target.value })}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Giới hạn tài liệu (doc_slugs, cách nhau bởi dấu phẩy)
                    </label>
                    <input
                      type="text"
                      value={draft.doc_slugs.join(', ')}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          doc_slugs: e.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean),
                        })
                      }
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Tiền tố đường dẫn (path_prefix)
                    </label>
                    <input
                      type="text"
                      value={draft.path_prefix ?? ''}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          path_prefix: e.target.value.trim() || null,
                        })
                      }
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-slate-100"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-4 pt-0.5">
                  <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={draft.is_regex}
                      onChange={(e) => setDraft({ ...draft, is_regex: e.target.checked })}
                      className="rounded border-slate-700"
                    />
                    <span>POSIX Regex (is_regex)</span>
                  </label>
                  <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={draft.case_sensitive}
                      onChange={(e) =>
                        setDraft({ ...draft, case_sensitive: e.target.checked })
                      }
                      className="rounded border-slate-700"
                    />
                    <span>Phân biệt hoa/thường (case_sensitive)</span>
                  </label>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">
                    Ghi chú (note)
                  </label>
                  <input
                    type="text"
                    value={draft.note}
                    onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-slate-100"
                  />
                </div>

                {/* Expected targets */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-medium text-slate-400">
                      Đích kỳ vọng (expected targets — cần khớp đủ tất cả mục)
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          expected: [...draft.expected, { doc_slug: '', path_suffix: '' }],
                        })
                      }
                      className="inline-flex items-center gap-1 text-[11px] text-brand-400 hover:underline"
                    >
                      <Plus className="h-3 w-3" /> Thêm đích
                    </button>
                  </div>
                  {draft.expected.map((exp, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        type="text"
                        value={exp.doc_slug}
                        onChange={(e) => updateExpected(idx, 'doc_slug', e.target.value)}
                        placeholder="doc_slug"
                        className="w-32 rounded border border-slate-700 bg-slate-950 px-2.5 py-1 font-mono text-xs text-slate-100"
                      />
                      <input
                        type="text"
                        value={exp.path_suffix}
                        onChange={(e) => updateExpected(idx, 'path_suffix', e.target.value)}
                        placeholder="path_suffix"
                        className="flex-1 rounded border border-slate-700 bg-slate-950 px-2.5 py-1 font-mono text-xs text-slate-100"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            expected: draft.expected.filter((_, i) => i !== idx),
                          })
                        }
                        className="text-slate-500 hover:text-rose-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top hits */}
              <div className="space-y-2 pt-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Top {draft.top_hits.length} kết quả truy xuất
                </h3>
                <div className="space-y-2">
                  {draft.top_hits.map((hit) => (
                    <div
                      key={`${hit.rank}-${hit.path}`}
                      className={`rounded-lg border p-3 text-xs ${
                        hit.matched
                          ? 'border-emerald-700 bg-emerald-950/30'
                          : 'border-slate-800 bg-slate-950'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-mono font-bold text-slate-200">
                            #{hit.rank}
                          </span>
                          <span className="truncate font-mono text-brand-300">
                            {hit.path}
                          </span>
                          <span className="font-mono text-[11px] text-slate-400">
                            L{hit.start_line}–{hit.end_line}
                          </span>
                        </div>
                        <span className="font-mono text-[11px] text-slate-400">
                          {hit.found_in}
                        </span>
                      </div>
                      <p className="mt-1.5 line-clamp-2 font-mono text-[11px] text-slate-300">
                        {hit.snippet}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-500">
              Chọn một mẫu đánh giá ở danh sách bên trái.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
