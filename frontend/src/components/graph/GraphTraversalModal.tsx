import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  Compass,
  GitBranch,
  Layers,
  Loader2,
  X,
} from 'lucide-react';
import { api } from '../../services/api';
import { GraphTraversalStep } from '../../types/api';

interface GraphTraversalModalProps {
  isOpen: boolean;
  onClose: () => void;
  docSlug: string;
  initialSourcePath: string;
  onSelectNode?: (path: string) => void;
}

export const GraphTraversalModal: React.FC<GraphTraversalModalProps> = ({
  isOpen,
  onClose,
  docSlug,
  initialSourcePath,
  onSelectNode,
}) => {
  const [sourcePath, setSourcePath] = useState(initialSourcePath);
  const [navDirection, setNavDirection] = useState<'OUTGOING' | 'INCOMING' | 'BOTH'>('BOTH');
  const [depthLimit, setDepthLimit] = useState<number>(2);
  const [limit, setLimit] = useState<number>(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<GraphTraversalStep[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSourcePath(initialSourcePath);
      setSteps([]);
      setError(null);
      setHasSearched(false);
      setLimit(20);
    }
  }, [isOpen, initialSourcePath]);

  const handleTraverse = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!sourcePath.trim() || !docSlug) return;

    setLoading(true);
    setError(null);
    try {
      const results = await api.traverseGraph(docSlug, {
        source_path: sourcePath.trim(),
        nav_direction: navDirection,
        depth_limit: depthLimit,
        limit: limit,
      });
      setSteps(results || []);
      setHasSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi duyệt đồ thị tri thức.');
      setSteps([]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-950/80 text-indigo-400 border border-indigo-700/60">
              <Compass className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-100">
                  Duyệt Đồ Thị Đa Tầng (Multi-Hop Graph Traversal)
                </h3>
                <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs font-mono font-semibold text-indigo-400 border border-indigo-500/30">
                  Stored Proc
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Thực thi stored procedure traverse_knowledge_graph trên PostgreSQL để khám phá liên kết đa tầng.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Configuration Controls Bar */}
        <form onSubmit={handleTraverse} className="border-b border-slate-800 bg-slate-950/40 p-5 space-y-3">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="flex-1 w-full">
              <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                Node Gốc Bắt Đầu Duyệt (Source LTree Path):
              </label>
              <input
                type="text"
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
                placeholder="ví dụ: doc_quy_trinh.sec_1.para_2"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-mono text-slate-100 focus:border-indigo-500 focus:outline-none"
                required
              />
            </div>

            <div className="w-full sm:w-44">
              <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                Hướng Duyệt Cạnh:
              </label>
              <select
                value={navDirection}
                onChange={(e) => setNavDirection(e.target.value as 'OUTGOING' | 'INCOMING' | 'BOTH')}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 focus:border-indigo-500 focus:outline-none"
              >
                <option value="BOTH">Hai chiều (BOTH)</option>
                <option value="OUTGOING">Đi ra (OUTGOING)</option>
                <option value="INCOMING">Đi vào (INCOMING)</option>
              </select>
            </div>

            <div className="w-full sm:w-28">
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-semibold text-slate-300">
                  Độ Sâu:
                </label>
                <span className="font-mono text-xs font-bold text-indigo-400">{depthLimit}</span>
              </div>
              <input
                type="range"
                min={1}
                max={5}
                value={depthLimit}
                onChange={(e) => setDepthLimit(Number(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
            </div>

            <div className="w-full sm:w-28">
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-semibold text-slate-300">
                  Giới Hạn:
                </label>
                <span className="font-mono text-xs font-bold text-indigo-400">{limit}</span>
              </div>
              <input
                type="range"
                min={1}
                max={100}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer"
              />
            </div>

            <div className="self-end pt-2 sm:pt-0">
              <button
                type="submit"
                disabled={loading || !sourcePath.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-indigo-500 disabled:opacity-50 transition"
              >
                {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitBranch className="h-3.5 w-3.5" />}
                <span>Duyệt</span>
              </button>
            </div>
          </div>
        </form>

        {/* Results Area */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {error && (
            <div className="rounded-xl border border-rose-800 bg-rose-950/60 p-3 text-xs text-rose-300">
              {error}
            </div>
          )}

          {loading && (
            <div className="py-16 text-center text-xs text-slate-400 animate-pulse space-y-2">
              <Loader2 className="mx-auto h-7 w-7 animate-spin text-indigo-400" />
              <p>Đang duyệt qua các bước nhảy trong đồ thị tri thức...</p>
            </div>
          )}

          {!loading && !hasSearched && (
            <div className="py-16 text-center text-xs text-slate-500 space-y-2">
              <Layers className="mx-auto h-8 w-8 text-slate-600" />
              <p className="font-medium text-slate-400">Chọn node gốc và bấm "Duyệt" để truy vết mạng lưới liên kết</p>
              <p className="text-[11px]">Hệ thống sẽ duyệt đồ thị BFS chống vòng lặp đệ quy qua stored procedure PostgreSQL.</p>
            </div>
          )}

          {!loading && hasSearched && steps.length === 0 && (
            <div className="py-16 text-center text-xs text-slate-400 space-y-2">
              <GitBranch className="mx-auto h-8 w-8 text-slate-600" />
              <p className="font-semibold text-slate-300">Không tìm thấy bước nhảy liên kết nào</p>
              <p className="text-[11px] text-slate-500">Node này chưa có cạnh quan hệ nào được lưu trong cơ sở dữ liệu đã công bố.</p>
            </div>
          )}

          {!loading && steps.length > 0 && (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs text-slate-400 pb-1 border-b border-slate-800">
                <span className="font-bold uppercase tracking-wider text-slate-300">
                  {steps.length} bước nhảy đồ thị được tìm thấy
                </span>
                <span className="font-mono text-[11px]">Gốc: {sourcePath}</span>
              </div>

              {steps.map((step, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5 hover:border-indigo-500/50 hover:bg-slate-900/80 transition flex flex-col gap-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-indigo-950 px-2 py-0.5 text-[10px] font-mono font-bold text-indigo-300 border border-indigo-800">
                        Bước nhảy {step.depth}
                      </span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono font-semibold text-slate-200 border border-slate-700">
                        {step.relation_type}
                      </span>
                    </div>

                    {onSelectNode && (
                      <button
                        type="button"
                        onClick={() => {
                          onSelectNode(step.target_path);
                          onClose();
                        }}
                        className="flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 hover:underline"
                      >
                        <span>Nhảy tới Chunk</span>
                        <ArrowRight className="h-3 w-3" />
                      </button>
                    )}
                  </div>

                  {/* Dual Path & Citation Breadcrumb */}
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded bg-slate-950 px-2 py-0.5 font-mono text-[11px] text-slate-400 border border-slate-800">
                      {step.source_path}
                    </span>
                    <ArrowRight className="h-3 w-3 text-slate-500" />
                    <span className="rounded bg-slate-950 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-300 border border-indigo-900/60">
                      {step.target_path}
                    </span>
                    <span className="rounded bg-slate-800/80 px-2 py-0.5 text-[10px] font-mono text-slate-400 border border-slate-700">
                      {step.target_doc_slug} · L{step.target_start_line}-L{step.target_end_line}
                    </span>
                  </div>

                  {/* Rationale if present */}
                  {step.rationale && (
                    <div className="rounded-lg bg-indigo-950/40 p-2.5 text-xs text-indigo-200 border border-indigo-800/50">
                      <span className="font-semibold text-indigo-400">Luận cứ: </span>
                      {step.rationale}
                    </div>
                  )}

                  {/* Contextualized text preferred, fallback to verbatim text */}
                  {(step.target_contextualized_text || step.target_text) && (
                    <div className="font-mono text-xs text-slate-300 bg-slate-950 p-2.5 rounded-lg border border-slate-800 line-clamp-3 leading-relaxed">
                      <div className="text-[10px] font-semibold text-slate-500 mb-1">Đoạn văn hoàn chỉnh:</div>
                      {step.target_contextualized_text || step.target_text}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 px-6 py-3 bg-slate-950/80 text-xs text-slate-400">
          <span>Hỗ trợ BFS sâu tới 5 tầng với chu trình chống lặp (Cycle Detection)</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-700 transition"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
