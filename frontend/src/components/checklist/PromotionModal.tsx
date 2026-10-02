import React, { useState } from 'react';
import { CheckCircle2, Database, Sparkles, X } from 'lucide-react';
import { PromoteSessionPayload, PromotionResultResponse } from '../../types/api';
import { StagingDocumentSession } from '../../types/staging';

interface PromotionModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: StagingDocumentSession;
  onPromote: (payload: PromoteSessionPayload) => Promise<PromotionResultResponse | null>;
}

export const PromotionModal: React.FC<PromotionModalProps> = ({
  isOpen,
  onClose,
  session,
  onPromote,
}) => {
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [computeEmbeddings, setComputeEmbeddings] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PromotionResultResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleExecute = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await onPromote({
        reviewer_notes: reviewerNotes.trim() || undefined,
        compute_embeddings: computeEmbeddings,
      });
      if (res && res.status === 'SUCCESS') {
        setResult(res);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi phê duyệt');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-brand-400" />
            <h3 className="text-base font-bold text-slate-100">
              Phê Duyệt & Chuyển Dữ Liệu Vào CSDL
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg bg-rose-950/80 p-3 text-xs text-rose-300 border border-rose-800">
            {error}
          </div>
        )}

        {result ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/60 p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400 mb-2" />
              <h4 className="text-sm font-bold text-emerald-200">
                Phê Duyệt & Nhập CSDL Thành Công!
              </h4>
              <p className="mt-1 text-xs text-emerald-300/80">
                Toàn bộ dữ liệu đã được ghi nguyên tử vào các bảng PostgreSQL production.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="rounded bg-slate-950 p-3 border border-slate-800">
                <span className="text-slate-500">Document UUID:</span>
                <p className="mt-1 font-semibold text-slate-200 break-all">{result.document_id}</p>
              </div>
              <div className="rounded bg-slate-950 p-3 border border-slate-800">
                <span className="text-slate-500">Số lượng Chunks:</span>
                <p className="mt-1 text-base font-bold text-brand-400">{result.chunks_promoted}</p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={onClose}
                className="rounded-lg bg-slate-800 px-5 py-2 text-xs font-semibold text-white hover:bg-slate-700"
              >
                Đóng
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {/* Session Summary Card */}
            <div className="rounded-lg bg-slate-950 p-4 border border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Văn bản:</span>
                <span className="font-bold text-slate-100 font-mono">{session.doc_slug}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Số lượng Chunks:</span>
                <span className="font-bold text-brand-400">{session.chunks.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Số lượng Cạnh Quan Hệ:</span>
                <span className="font-bold text-blue-400">{session.edges.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Ngày hiệu lực:</span>
                <span className="text-slate-200 font-mono">{session.valid_from || 'Chưa đặt'}</span>
              </div>
            </div>

            {/* Reviewer Notes */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Ghi Chú Thẩm Định Của Chuyên Viên (Audit Notes)
              </label>
              <textarea
                rows={3}
                value={reviewerNotes}
                onChange={(e) => setReviewerNotes(e.target.value)}
                placeholder="Nhập ý kiến thẩm định hoặc số quyết định ban hành..."
                className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
              />
            </div>

            {/* Embeddings Toggle */}
            <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
              <input
                type="checkbox"
                id="embCheck"
                checked={computeEmbeddings}
                onChange={(e) => setComputeEmbeddings(e.target.checked)}
                className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="embCheck" className="text-xs text-slate-300 cursor-pointer">
                <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-brand-400" />
                  Tính toán Vector Embeddings (512-dim pgvector)
                </span>
                <span className="block text-[11px] text-slate-500">
                  Tự động sinh dense vector embedding phục vụ MCP hybrid search
                </span>
              </label>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleExecute}
                disabled={loading}
                className="rounded-lg bg-brand-600 px-5 py-2 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50 shadow-md"
              >
                {loading ? 'Đang ghi vào PostgreSQL...' : 'Xác Nhận Promotion'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
