import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { StagingChunk } from '../../types/staging';

interface AddChunkModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (chunk: StagingChunk) => Promise<boolean>;
  parentPath?: string;
}

export const AddChunkModal: React.FC<AddChunkModalProps> = ({
  isOpen,
  onClose,
  onAdd,
  parentPath = '',
}) => {
  const [path, setPath] = useState(parentPath ? `${parentPath}.` : '');
  const [nodeType, setNodeType] = useState('PARAGRAPH');
  const [startLine, setStartLine] = useState<number>(1);
  const [endLine, setEndLine] = useState<number>(1);
  const [verbatimText, setVerbatimText] = useState('');
  const [contextualizedText, setContextualizedText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  // Helper to synthesize hierarchical lineage breadcrumb chain
  const getBreadcrumbPrefix = (p: string) => {
    if (!p) return '';
    const parts = p.split('.').filter(Boolean);
    if (parts.length <= 1) return '';
    const ancestors = parts.slice(0, -1);
    return `[${ancestors.join(' > ')}]`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim() || !verbatimText.trim()) {
      setError('Vui lòng nhập đường dẫn path và nội dung nguyên văn.');
      return;
    }
    if (startLine < 1 || endLine < startLine) {
      setError('Tọa độ dòng không hợp lệ: start_line phải >= 1 và end_line phải >= start_line.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const prefix = getBreadcrumbPrefix(path.trim());
      const synthesizedContext =
        contextualizedText.trim() ||
        (prefix ? `${prefix}\n${verbatimText.trim()}` : verbatimText.trim());

      const newChunk: StagingChunk = {
        path: path.trim(),
        node_type: nodeType,
        verbatim_text: verbatimText.trim(),
        contextualized_text: synthesizedContext,
        start_line: startLine,
        end_line: endLine,
        review_status: 'PENDING',
        finalization_state: 'UNFINALIZED',
        metadata: {
          node_type: nodeType,
        },
      };
      const ok = await onAdd(newChunk);
      if (ok) {
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi thêm mục');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Plus className="h-5 w-5 text-brand-400" />
            <h3 className="text-base font-bold text-slate-100">
              Thêm Mục Mới Vào Cây Phân Cấp
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

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Đường Dẫn LTree (Path) <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="ví dụ: doc_slug.section_1.sub_1.node_1"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Loại Mục AST (Node Type)
              </label>
              <select
                value={nodeType}
                onChange={(e) => setNodeType(e.target.value)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="SECTION">SECTION (Tiêu đề mục)</option>
                <option value="PARAGRAPH">PARAGRAPH (Đoạn văn)</option>
                <option value="TABLE">TABLE (Bảng biểu)</option>
                <option value="CODE">CODE (Khối mã lệnh)</option>
                <option value="LIST">LIST (Danh sách)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Dòng Bắt Đầu (Start Line) <span className="text-rose-400">*</span>
              </label>
              <input
                type="number"
                min={1}
                value={startLine}
                onChange={(e) => setStartLine(parseInt(e.target.value, 10) || 1)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Dòng Kết Thúc (End Line) <span className="text-rose-400">*</span>
              </label>
              <input
                type="number"
                min={1}
                value={endLine}
                onChange={(e) => setEndLine(parseInt(e.target.value, 10) || 1)}
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Nội Dung Nguyên Văn (Verbatim Text) <span className="text-rose-400">*</span>
            </label>
            <textarea
              rows={4}
              value={verbatimText}
              onChange={(e) => setVerbatimText(e.target.value)}
              placeholder="Nội dung chính xác của mục..."
              className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono leading-relaxed"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Văn Cảnh Tổng Hợp (Contextualized Text)
            </label>
            <textarea
              rows={3}
              value={contextualizedText}
              onChange={(e) => setContextualizedText(e.target.value)}
              placeholder="Tiền tố phân cảnh (để trống sẽ tự động lấy theo verbatim)..."
              className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50"
            >
              {loading ? 'Đang thêm...' : 'Lưu Mục'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
