import React, { useEffect, useState } from 'react';
import { Check, Edit3, Save, Sparkles, X } from 'lucide-react';
import { StagingChunk } from '../../types/staging';
import { DocumentTreeNode } from '../../types/tree';

interface SurgicalEditorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  selectedNode: DocumentTreeNode | null;
  onSaveChunk: (chunk: StagingChunk) => Promise<boolean>;
}

export const SurgicalEditorDrawer: React.FC<SurgicalEditorDrawerProps> = ({
  isOpen,
  onClose,
  selectedNode,
  onSaveChunk,
}) => {
  const [path, setPath] = useState('');
  const [verbatimText, setVerbatimText] = useState('');
  const [contextualizedText, setContextualizedText] = useState('');
  const [metadataJson, setMetadataJson] = useState('{}');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (selectedNode) {
      setPath(selectedNode.path || '');
      setVerbatimText(selectedNode.verbatim_text || '');
      setContextualizedText(selectedNode.contextualized_text || '');
      setMetadataJson(
        JSON.stringify(selectedNode.metadata || {}, null, 2)
      );
      setError(null);
      setSuccess(false);
    }
  }, [selectedNode]);

  if (!isOpen || !selectedNode) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    let parsedMeta: Record<string, unknown> = {};
    try {
      if (metadataJson.trim()) {
        parsedMeta = JSON.parse(metadataJson);
      }
    } catch {
      setError('Định dạng Metadata JSON không hợp lệ.');
      return;
    }

    setLoading(true);
    try {
      const updatedChunk: StagingChunk = {
        path: path.trim(),
        verbatim_text: verbatimText.trim(),
        contextualized_text: contextualizedText.trim(),
        start_line: selectedNode.start_line,
        end_line: selectedNode.end_line,
        metadata: parsedMeta,
      };

      const ok = await onSaveChunk(updatedChunk);
      if (ok) {
        setSuccess(true);
        setTimeout(() => {
          onClose();
        }, 600);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi lưu chỉnh sửa');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-slate-800 bg-slate-900 shadow-2xl backdrop-blur-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div className="flex items-center gap-2">
          <Edit3 className="h-5 w-5 text-brand-400" />
          <div>
            <h3 className="text-sm font-bold text-slate-100">
              Hiệu Chỉnh Phẫu Thuật Điều Khoản (Surgical Editor)
            </h3>
            <p className="text-[11px] text-slate-400">
              Chỉnh sửa trực tiếp text nguyên văn, ngữ cảnh CPHC, và siêu dữ liệu
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mx-6 mt-4 rounded-lg bg-rose-950/80 p-3 text-xs text-rose-300 border border-rose-800">
          {error}
        </div>
      )}
      {success && (
        <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg bg-emerald-950/80 p-3 text-xs text-emerald-300 border border-emerald-800">
          <Check className="h-4 w-4 text-emerald-400" />
          <span>Đã lưu thành công và cập nhật vào file Staging!</span>
        </div>
      )}

      {/* Form Content */}
      <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* LTree Path */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Đường Dẫn LTree (Path)
          </label>
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-mono text-slate-100 focus:border-brand-500 focus:outline-none"
            required
          />
        </div>

        {/* Verbatim Text */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Văn Bản Nguyên Văn (Verbatim Text)
          </label>
          <textarea
            rows={6}
            value={verbatimText}
            onChange={(e) => setVerbatimText(e.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs font-mono text-slate-100 leading-relaxed focus:border-brand-500 focus:outline-none"
            required
          />
        </div>

        {/* Contextualized Text */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-semibold text-slate-300">
              Văn Cảnh CPHC Tổng Hợp (Contextualized Text)
            </label>
            <button
              type="button"
              onClick={() => setContextualizedText(verbatimText)}
              className="text-[11px] text-brand-400 hover:underline flex items-center gap-1"
            >
              <Sparkles className="h-3 w-3" />
              <span>Đồng bộ từ Verbatim</span>
            </button>
          </div>
          <textarea
            rows={4}
            value={contextualizedText}
            onChange={(e) => setContextualizedText(e.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs font-mono text-slate-100 leading-relaxed focus:border-brand-500 focus:outline-none"
          />
        </div>

        {/* Dynamic Metadata JSON */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Siêu Dữ Liệu Ngữ Nghĩa (Metadata JSON)
          </label>
          <textarea
            rows={4}
            value={metadataJson}
            onChange={(e) => setMetadataJson(e.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-950 p-3 text-xs font-mono text-slate-200 focus:border-brand-500 focus:outline-none"
          />
        </div>
      </form>

      {/* Footer */}
      <div className="flex items-center justify-end gap-3 border-t border-slate-800 px-6 py-4 bg-slate-900/90">
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white"
        >
          Đóng
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-5 py-2 text-xs font-semibold text-white hover:bg-brand-500 disabled:opacity-50 shadow-md"
        >
          <Save className="h-4 w-4" />
          <span>{loading ? 'Đang lưu...' : 'Lưu Thay Đổi'}</span>
        </button>
      </div>
    </div>
  );
};
