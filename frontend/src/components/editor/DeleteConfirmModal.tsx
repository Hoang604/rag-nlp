import React from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  path: string;
  loading?: boolean;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  path,
  loading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-xl border border-rose-900/60 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-rose-950 p-2 text-rose-400 border border-rose-800 shrink-0">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-100">
              Xác Nhận Xóa Điều Khoản
            </h3>
            <p className="mt-2 text-xs text-slate-300 leading-relaxed">
              Bạn có chắc chắn muốn xóa điều khoản có đường dẫn:
            </p>
            <div className="mt-2 rounded bg-slate-950 p-2 font-mono text-xs text-rose-300 border border-slate-800 break-all">
              {path}
            </div>
            <p className="mt-2 text-[11px] text-amber-400">
              Cảnh báo: Nếu điều khoản này có các mục con hoặc cạnh liên kết, việc xóa có thể tạo ra lỗi mồ côi (Orphan chunks).
            </p>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white"
          >
            Hủy Bỏ
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>{loading ? 'Đang xóa...' : 'Xác Nhận Xóa'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
