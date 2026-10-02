import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { CreateEdgePayload } from '../../types/api';

interface EdgeEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddEdge: (edge: CreateEdgePayload) => Promise<boolean>;
  defaultSourcePath?: string;
  initialSourcePath?: string;
}

export const EdgeEditorModal: React.FC<EdgeEditorModalProps> = ({
  isOpen,
  onClose,
  onAddEdge,
  defaultSourcePath = '',
  initialSourcePath = '',
}) => {
  const [sourcePath, setSourcePath] = useState(initialSourcePath || defaultSourcePath);
  const [targetPath, setTargetPath] = useState('');
  const [targetExternalRef, setTargetExternalRef] = useState('');
  const [relationType, setRelationType] = useState('REFERENCES');
  const [citationText, setCitationText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const relationTypes = [
    { key: 'MODIFIES_AND_REPLACES', label: 'Sửa đổi & Thay thế (MODIFIES_AND_REPLACES)' },
    { key: 'SANCTIONS', label: 'Xử phạt (SANCTIONS)' },
    { key: 'HAS_ADDITIONAL_SANCTION', label: 'Phạt bổ sung (HAS_ADDITIONAL_SANCTION)' },
    { key: 'REFERENCES', label: 'Dẫn chiếu pháp luật (REFERENCES)' },
    { key: 'REFERENCES_TECHNICAL_STANDARD', label: 'Dẫn chiếu Quy chuẩn kỹ thuật (QCVN)' },
    { key: 'OVERRIDES', label: 'Ghi đè ưu tiên (OVERRIDES)' },
    { key: 'EXEMPTS', label: 'Miễn trừ / Đặc cách (EXEMPTS)' },
    { key: 'GUIDES', label: 'Hướng dẫn thi hành (GUIDES)' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourcePath.trim()) {
      setError('Vui lòng nhập source_path.');
      return;
    }
    if (!targetPath.trim() && !targetExternalRef.trim()) {
      setError('Vui lòng nhập target_path nội bộ hoặc trích dẫn target_external_ref.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: CreateEdgePayload = {
        source_path: sourcePath.trim(),
        target_path: targetPath.trim() || null,
        target_external_ref: targetExternalRef.trim() || null,
        relation_type: relationType,
        citation_text: citationText.trim() || null,
        metadata: {},
      };
      const ok = await onAddEdge(payload);
      if (ok) {
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi tạo quan hệ pháp lý');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Plus className="h-5 w-5 text-blue-400" />
            <h3 className="text-base font-bold text-slate-100">
              Tạo Cạnh Quan Hệ Pháp Lý (Graph Edge)
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
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Đường Dẫn Nguồn (Source Path) <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              placeholder="ví dụ: 100_2019_nd_cp.c_ii.a_5.c_3.p_a"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-blue-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Loại Quan Hệ Pháp Lý (Relation Type)
            </label>
            <select
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
            >
              {relationTypes.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Đường Dẫn Đích Nội Bộ (Target Path)
            </label>
            <input
              type="text"
              value={targetPath}
              onChange={(e) => setTargetPath(e.target.value)}
              placeholder="ví dụ: 100_2019_nd_cp.c_ii.a_5.c_1.p_a hoặc doc_qcvn_41.p_127"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Trích Dẫn Ngoại Bộ (Target External Ref - nếu chưa ingest)
            </label>
            <input
              type="text"
              value={targetExternalRef}
              onChange={(e) => setTargetExternalRef(e.target.value)}
              placeholder="ví dụ: Quy chuẩn QCVN 41:2019/BGTVT"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Nguyên Văn Cụm Dẫn Chiếu (Citation Text)
            </label>
            <input
              type="text"
              value={citationText}
              onChange={(e) => setCitationText(e.target.value)}
              placeholder="ví dụ: theo quy định tại Điểm a Khoản 1 Điều này"
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
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
              className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? 'Đang lưu...' : 'Thêm Cạnh Quan Hệ'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
