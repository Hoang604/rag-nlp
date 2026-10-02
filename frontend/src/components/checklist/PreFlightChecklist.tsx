import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  ShieldCheck,
} from 'lucide-react';
import { PreFlightValidationResponse } from '../../types/preflight';
import { StagingDocumentSession } from '../../types/staging';

interface PreFlightChecklistProps {
  session: StagingDocumentSession;
  validationResult: PreFlightValidationResponse | null;
  validating: boolean;
  onReValidate: () => void;
  onOpenPromotionModal: () => void;
}

export const PreFlightChecklist: React.FC<PreFlightChecklistProps> = ({
  session,
  validationResult,
  validating,
  onReValidate,
  onOpenPromotionModal,
}) => {
  const issues = validationResult?.issues || [];
  const blockingIssues = issues.filter((i) => i.blocking);
  const warningIssues = issues.filter((i) => !i.blocking);
  const isPassed = validationResult?.passed ?? false;

  const totalChunks = session.chunks.length;
  const finalizedChunks = session.chunks.filter(
    (c) => c.review_status === 'REVIEWED'
  ).length;
  const pendingChunks = totalChunks - finalizedChunks;

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-slate-950 p-6 space-y-6">
      {/* Top Banner: Verdict Status */}
      <div
        className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border p-5 shadow-lg ${
          isPassed
            ? 'border-emerald-700/80 bg-emerald-950/40 text-emerald-100'
            : 'border-rose-800/80 bg-rose-950/40 text-rose-100'
        }`}
      >
        <div className="flex items-center gap-4">
          <div
            className={`flex h-12 w-12 flex-none items-center justify-center rounded-xl border shadow-inner ${
              isPassed
                ? 'bg-emerald-900 text-emerald-300 border border-emerald-700'
                : 'bg-rose-900 text-rose-300 border border-rose-700'
            }`}
          >
            {isPassed ? (
              <ShieldCheck className="h-7 w-7" />
            ) : (
              <AlertCircle className="h-7 w-7" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-slate-300">
                {session.doc_slug}
              </span>
              <span className="text-slate-500">•</span>
              <span className="text-xs text-slate-400 truncate max-w-md">
                {session.title}
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-100 mt-1">
              {isPassed
                ? 'Đạt Toàn Bộ Tiêu Chuẩn Thẩm Định Tính Toàn Vẹn!'
                : `Phát Hiện ${blockingIssues.length} Lỗi Chặn Phê Duyệt`}
            </h3>
            <p className="text-xs text-slate-300 mt-0.5">
              {isPassed
                ? 'Văn bản đáp ứng đầy đủ tính toàn vẹn cấu trúc AST, quan hệ pháp lý và dữ liệu.'
                : 'Vui lòng chỉnh sửa các lỗi chặn bên dưới trước khi phê duyệt vào CSDL PostgreSQL.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-none self-end sm:self-center">
          <button
            type="button"
            onClick={onReValidate}
            disabled={validating}
            className="rounded-lg border border-slate-700 bg-slate-900/90 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
          >
            {validating ? 'Đang kiểm tra...' : 'Kiểm Tra Lại'}
          </button>
          <button
            type="button"
            onClick={onOpenPromotionModal}
            disabled={!isPassed}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-950 transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span>Tiến Hành Phê Duyệt</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Progress Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Tiến độ rà soát điều khoản</span>
            <CheckCircle className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold text-slate-100">
              {finalizedChunks}
            </span>
            <span className="text-xs text-slate-400 font-mono">/ {totalChunks} mục</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {pendingChunks > 0
              ? `Còn ${pendingChunks} mục ở trạng thái PENDING`
              : '100% mục đã được rà soát'}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Lỗi chặn phê duyệt (Blocking)</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <span className="font-mono text-2xl font-bold text-rose-400">
            {blockingIssues.length}
          </span>
          <p className="mt-1 text-[11px] text-slate-500">
            Bắt buộc phải khắc phục về 0 để promote
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Cảnh báo khuyến nghị</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <span className="font-mono text-2xl font-bold text-amber-400">
            {warningIssues.length}
          </span>
          <p className="mt-1 text-[11px] text-slate-500">
            Không chặn phê duyệt nhưng nên lưu ý
          </p>
        </div>
      </div>

      {/* Issues Breakdown List */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow space-y-4">
        <h4 className="text-sm font-bold text-slate-100">
          Danh Sách Vấn Đề Thẩm Định Chi Tiết ({issues.length})
        </h4>

        {issues.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center text-xs text-slate-400">
            <ShieldCheck className="mx-auto mb-2 h-8 w-8 text-emerald-400" />
            <p className="font-semibold text-slate-200">Không có vi phạm toàn vẹn nào</p>
            <p className="mt-0.5 text-slate-500">
              Văn bản đạt chuẩn toàn bộ quy tắc thẩm định tính toàn vẹn.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {issues.map((issue, idx) => {
              const isBlocking = issue.blocking;
              return (
                <div
                  key={`${issue.rule}-${issue.path || idx}`}
                  className={`flex items-start gap-3 rounded-lg border p-3 text-xs ${
                    isBlocking
                      ? 'border-rose-900/80 bg-rose-950/30 text-rose-200'
                      : 'border-amber-900/80 bg-amber-950/30 text-amber-200'
                  }`}
                >
                  <div className="mt-0.5 flex-none">
                    {isBlocking ? (
                      <AlertCircle className="h-4 w-4 text-rose-400" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-amber-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono font-bold text-[11px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-950/80 border border-slate-800">
                        {issue.rule}
                      </span>
                      {issue.path && (
                        <span className="font-mono text-[10px] text-slate-400">
                          {issue.path}
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${
                          isBlocking
                            ? 'bg-rose-900/60 text-rose-300'
                            : 'bg-amber-900/60 text-amber-300'
                        }`}
                      >
                        {isBlocking ? 'Chặn Phê Duyệt' : 'Cảnh Báo'}
                      </span>
                    </div>
                    <p className="text-slate-200 leading-relaxed">{issue.message}</p>
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
