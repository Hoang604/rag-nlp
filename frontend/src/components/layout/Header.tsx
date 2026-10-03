import React, { useState } from 'react';
import {
  CheckCircle,
  ExternalLink,
  FilePlus,
  Layers,
  RefreshCw,
  RotateCcw,
  Scale,
  Search,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { StagingDocumentSession, StagingSessionSummary } from '../../types/staging';
import { StatusBadge } from './StatusBadge';

interface HeaderProps {
  showDocPicker?: boolean;
  sessions: StagingSessionSummary[];
  activeDocSlug?: string;
  session: StagingDocumentSession | null;
  onSelectDoc: (docSlug: string) => void;
  onRefresh: () => void;
  onOpenPromotionModal: () => void;
  onOpenCreateSessionModal: () => void;
  onQuickValidate: () => void;
  onReopenSession?: () => void;
  onDeleteSession?: () => void;
  onOpenBacklogModal?: () => void;
  onOpenGlobalGrep?: () => void;
  validating?: boolean;
  blockingIssuesCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  showDocPicker = true,
  sessions,
  activeDocSlug,
  session,
  onSelectDoc,
  onRefresh,
  onOpenPromotionModal,
  onOpenCreateSessionModal,
  onQuickValidate,
  onReopenSession,
  onDeleteSession,
  onOpenBacklogModal,
  onOpenGlobalGrep,
  validating = false,
  blockingIssuesCount = 0,
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  const unresolvedExternalRefsCount = session?.edges?.filter(
    (e) => !e.target_path || !session.chunks?.some((c) => c.path === e.target_path)
  ).length || 0;

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/95 px-5 py-3 shadow-md">
      {/* Brand & Document Selector */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-inner">
            <Scale className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-wide text-slate-100">
                RAG REVIEWER STUDIO
              </span>
              <span className="rounded bg-brand-950 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-brand-400 border border-brand-800/60">
                v1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Human-in-the-Loop Document Ingestion &amp; Reviewer
            </p>
          </div>
        </div>

        {showDocPicker && (
          <>
        <div className="h-6 w-px bg-slate-800 hidden sm:block" />

        {/* Document Selection Dropdown */}
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-slate-400" />
          <select
            value={activeDocSlug || ''}
            onChange={(e) => onSelectDoc(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs md:text-sm font-medium text-slate-100 shadow-sm transition hover:border-slate-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {sessions.length === 0 ? (
              <option value="">Chưa có tài liệu trong Staging</option>
            ) : (
              sessions.map((s) => (
                <option key={s.doc_slug} value={s.doc_slug}>
                  {s.doc_slug} — {s.title.substring(0, 38)}
                  {s.title.length > 38 ? '...' : ''} ({s.status})
                </option>
              ))
            )}
          </select>

          <button
            onClick={handleRefresh}
            title="Làm mới danh sách tài liệu"
            className="rounded-lg border border-slate-700 bg-slate-800 p-2 text-slate-300 transition hover:bg-slate-700 hover:text-white"
          >
            <RefreshCw
              className={`h-4 w-4 ${isRefreshing ? 'animate-spin text-brand-400' : ''}`}
            />
          </button>
        </div>
          </>
        )}
      </div>

      {/* Center / Right Metadata & Action Buttons */}
      <div className="flex items-center gap-3">
        {/* Unresolved External References Interactive Button */}
        {unresolvedExternalRefsCount > 0 && (
          <button
            type="button"
            onClick={onOpenBacklogModal}
            className="flex items-center gap-1.5 rounded-lg border border-amber-800/70 bg-amber-950/60 px-2.5 py-1 text-[11px] font-medium text-amber-300 hover:bg-amber-900/60 transition shadow cursor-pointer"
            title={`${unresolvedExternalRefsCount} liên kết tham chiếu trỏ sang tài liệu ngoài chưa giải quyết. Bấm để quản lý backlog.`}
          >
            <ExternalLink className="h-3 w-3 text-amber-400" />
            <span>{unresolvedExternalRefsCount} ref ngoại</span>
          </button>
        )}

        {/* Global Grep Search Button */}
        {session && onOpenGlobalGrep && (
          <button
            type="button"
            onClick={onOpenGlobalGrep}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition"
            title="Tìm kiếm toàn văn in-memory grep (Ctrl+K)"
          >
            <Search className="h-3.5 w-3.5 text-brand-400" />
            <span className="hidden sm:inline">Tìm kiếm</span>
            <span className="hidden md:inline rounded bg-slate-900 px-1 py-0.2 text-[9px] font-mono text-slate-400 border border-slate-750">
              Ctrl+K
            </span>
          </button>
        )}

        {/* Document Ingestion Metadata Chip */}
        {session && session.metadata && Object.keys(session.metadata).length > 0 && (
          <div className="hidden xl:flex items-center gap-2 rounded-lg bg-slate-800/80 px-2.5 py-1 border border-slate-700 text-[11px] text-slate-300 font-mono">
            {Boolean(session.metadata.format) && (
              <span className="font-bold text-brand-300 uppercase">
                {String(session.metadata.format)}
              </span>
            )}
            {session.metadata.total_lines !== undefined && (
              <>
                <span className="text-slate-600">•</span>
                <span>{String(session.metadata.total_lines)} dòng</span>
              </>
            )}
            {session.metadata.tables_count !== undefined && (
              <>
                <span className="text-slate-600">•</span>
                <span>{String(session.metadata.tables_count)} bảng</span>
              </>
            )}
            {Boolean(session.metadata.file_name || session.metadata.original_filename) && (
              <>
                <span className="text-slate-600">•</span>
                <span
                  className="truncate max-w-[140px] text-slate-400"
                  title={String(session.metadata.file_name || session.metadata.original_filename)}
                >
                  {String(session.metadata.file_name || session.metadata.original_filename)}
                </span>
              </>
            )}
          </div>
        )}
        {session && session.chunks.length > 0 && (
          <div className="hidden lg:flex items-center gap-2 rounded-lg bg-slate-800/80 px-2.5 py-1 border border-slate-700">
            <span className="text-[11px] text-slate-400">Tiến độ rà soát:</span>
            <div className="w-16 h-1.5 rounded-full bg-slate-900 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{
                  width: `${
                    session.chunks.length > 0
                      ? Math.round(
                          (session.chunks.filter((c) => c.review_status === 'REVIEWED').length /
                            session.chunks.length) *
                            100
                        )
                      : 0
                  }%`,
                }}
              />
            </div>
            <span className="font-mono text-[11px] font-bold text-emerald-400">
              {session.chunks.filter((c) => c.review_status === 'REVIEWED').length}/
              {session.chunks.length} (
              {session.chunks.length > 0
                ? Math.round(
                    (session.chunks.filter((c) => c.review_status === 'REVIEWED').length /
                      session.chunks.length) *
                      100
                  )
                : 0}
              %)
            </span>
          </div>
        )}
        {session && <StatusBadge status={session.status} />}

        {/* Quick Validate Button */}
        {session && (
          <button
            onClick={onQuickValidate}
            disabled={validating}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-slate-700 disabled:opacity-50"
          >
            <CheckCircle
              className={`h-3.5 w-3.5 ${validating ? 'animate-spin text-brand-400' : 'text-slate-400'}`}
            />
            <span>{validating ? 'Đang kiểm tra...' : 'Kiểm tra'}</span>
          </button>
        )}

        {/* Promote to PostgreSQL Button */}
        {session && session.status !== 'PROMOTED' && (
          <button
            onClick={onOpenPromotionModal}
            disabled={blockingIssuesCount > 0}
            className={`flex items-center gap-2 rounded-lg px-4 py-1.5 text-xs font-semibold shadow transition ${
              blockingIssuesCount > 0
                ? 'cursor-not-allowed border border-rose-800/80 bg-rose-950/40 text-rose-300 opacity-60'
                : 'border border-brand-500 bg-gradient-to-r from-brand-600 to-brand-700 text-white hover:from-brand-500 hover:to-brand-600 shadow-brand-900/30'
            }`}
          >
            {blockingIssuesCount > 0 ? (
              <>
                <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                <span>Bị chặn ({blockingIssuesCount} lỗi)</span>
              </>
            ) : (
              <>
                <CheckCircle className="h-3.5 w-3.5 text-white" />
                <span>Xác nhận & Lưu trữ</span>
              </>
            )}
          </button>
        )}

        {/* Reopen Promoted Session Button (AMENDMENT) */}
        {session && session.status === 'PROMOTED' && onReopenSession && (
          <button
            onClick={onReopenSession}
            className="flex items-center gap-1.5 rounded-lg border border-amber-600/60 bg-amber-950/40 px-3 py-1.5 text-xs font-semibold text-amber-200 transition hover:bg-amber-900/60 shadow"
            title="Mở lại tài liệu đã lưu trữ sang trạng thái AMENDMENT để chỉnh sửa và vá lỗi"
          >
            <RotateCcw className="h-3.5 w-3.5 text-amber-400" />
            <span>Mở lại sửa đổi</span>
          </button>
        )}

        {/* Delete / Discard Staging Session Button */}
        {session && onDeleteSession && (
          <button
            onClick={onDeleteSession}
            className="flex items-center gap-1.5 rounded-lg border border-rose-900/60 bg-rose-950/40 px-3 py-1.5 text-xs font-medium text-rose-300 transition hover:bg-rose-900/60 hover:text-white"
            title="Hủy bỏ và xóa vĩnh viễn phiên làm việc này khỏi Vùng đệm Staging"
          >
            <Trash2 className="h-3.5 w-3.5 text-rose-400" />
            <span className="hidden sm:inline">Hủy phiên</span>
          </button>
        )}

        {/* New Session Button */}
        <button
          onClick={onOpenCreateSessionModal}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-slate-700 hover:text-white"
        >
          <FilePlus className="h-3.5 w-3.5 text-brand-400" />
          <span>Tài liệu mới</span>
        </button>
      </div>
    </header>
  );
};
