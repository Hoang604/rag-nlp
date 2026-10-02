import React, { useRef, useState } from 'react';
import {
  CheckCircle2,
  FileCode,
  FileText,
  Loader2,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react';
import { api } from '../../services/api';
import { useToast } from '../toast/ToastContext';

interface CreateSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newDocSlug: string) => Promise<void>;
}

export const CreateSessionModal: React.FC<CreateSessionModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { success, error } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeTab, setActiveTab] = useState<'upload' | 'paste'>('upload');
  const [docSlug, setDocSlug] = useState('');
  const [docTitle, setDocTitle] = useState('');
  const [rawText, setRawText] = useState('');
  const [validFrom, setValidFrom] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [validTo, setValidTo] = useState('');

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileSize, setSelectedFileSize] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  // Auto-extract doc_slug and title from filename
  const autoInferMetadataFromFileName = (fileName: string) => {
    const baseName = fileName.replace(/\.[^/.]+$/, '').trim();
    setSelectedFileName(fileName);

    const inferredSlug = baseName.toLowerCase().replace(/[^a-z0-9_-]/g, '-');
    if (!docSlug) setDocSlug(inferredSlug);
    if (!docTitle) setDocTitle(`Văn bản: ${baseName}`);
  };

  const processFile = async (file: File) => {
    setSelectedFileSize(`${(file.size / 1024).toFixed(1)} KB`);
    autoInferMetadataFromFileName(file.name);

    try {
      const text = await file.text();
      if (!text.trim()) {
        error('File rỗng', 'File bạn chọn không có nội dung text.');
        return;
      }
      setRawText(text);
      success('Tải file thành công', `Đã nạp ${text.length.toLocaleString('vi-VN')} ký tự từ file '${file.name}'.`);
    } catch (err) {
      error('Lỗi đọc file', err instanceof Error ? err.message : 'Không thể đọc nội dung file');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await processFile(file);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      await processFile(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docSlug.trim()) {
      error('Thiếu thông tin', 'Vui lòng nhập định danh văn bản (doc_slug).');
      return;
    }
    if (!rawText.trim()) {
      error('Thiếu nội dung', 'Vui lòng tải file hoặc dán nội dung toàn văn văn bản.');
      return;
    }

    setLoading(true);
    try {
      await api.createSessionRaw({
        doc_slug: docSlug.trim(),
        title: docTitle.trim() || docSlug.trim(),
        raw_text: rawText,
        valid_from: validFrom || undefined,
        valid_to: validTo || undefined,
      });

      success(
        'Bóc tách AST & CPHC thành công!',
        `Đã tạo phiên Staging cho văn bản '${docSlug.trim()}'. Đang mở giao diện kiểm duyệt...`
      );
      await onSuccess(docSlug.trim());
      onClose();
    } catch (err) {
      error('Lỗi khởi tạo phiên Staging', err instanceof Error ? err.message : 'Lỗi hệ thống');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-fade-in">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600/20 text-brand-400 border border-brand-500/30">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">
                Khởi Tạo Staging & Bóc Tách AST Tự Động
              </h3>
              <p className="text-xs text-slate-400">
                Nạp văn bản vào vùng đệm để thẩm định và gán quan hệ
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mode Tabs */}
        <div className="flex border-b border-slate-800 bg-slate-950/60 px-6 pt-3">
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
              activeTab === 'upload'
                ? 'border-brand-500 text-brand-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <UploadCloud className="h-4 w-4" />
            <span>Kéo Thả & Tải Lên File (.txt, .md, .json)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('paste')}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
              activeTab === 'paste'
                ? 'border-brand-500 text-brand-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="h-4 w-4" />
            <span>Dán Toàn Văn Trực Tiếp</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Metadata Row: doc_slug & title */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Định Danh Văn Bản (doc_slug) <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={docSlug}
                onChange={(e) => setDocSlug(e.target.value)}
                placeholder="ví dụ: 100-2019-nd-cp hoặc quy-che-tuyen-sinh"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Tiêu Đề Trích Yếu Văn Bản
              </label>
              <input
                type="text"
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="ví dụ: Quy chế tuyển sinh đại học..."
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Dates Row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Ngày Bắt Đầu Hiệu Lực (valid_from) <span className="text-rose-400">*</span>
              </label>
              <input
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Ngày Hết Hiệu Lực (valid_to) (để trống nếu vô thời hạn)
              </label>
              <input
                type="date"
                value={validTo}
                onChange={(e) => setValidTo(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Upload Dropzone Tab */}
          {activeTab === 'upload' && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Tệp Tin Văn Bản Gốc
              </label>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition ${
                  isDragging
                    ? 'border-brand-400 bg-brand-950/40'
                    : selectedFileName
                    ? 'border-emerald-600/70 bg-emerald-950/20'
                    : 'border-slate-700 bg-slate-950/60 hover:border-slate-500 hover:bg-slate-950'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.md,.json,.text"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {selectedFileName ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="rounded-full bg-emerald-900/40 p-3 text-emerald-400 border border-emerald-700/60">
                      <CheckCircle2 className="h-6 w-6" />
                    </div>
                    <span className="font-semibold text-xs text-slate-100">
                      {selectedFileName}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      {selectedFileSize} • {rawText.length.toLocaleString('vi-VN')} ký tự
                    </span>
                    <p className="text-[11px] text-brand-400 hover:underline mt-1">
                      Bấm để chọn file khác
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="rounded-full bg-slate-900 p-3 text-slate-400 border border-slate-800">
                      <UploadCloud className="h-6 w-6 text-brand-400" />
                    </div>
                    <p className="text-xs font-semibold text-slate-200">
                      Kéo thả file vào đây hoặc <span className="text-brand-400 underline">bấm để duyệt</span>
                    </p>
                    <p className="text-[11px] text-slate-400">
                      Hỗ trợ định dạng văn bản nguyên văn (.txt, .md, .json)
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Paste Raw Text Tab */}
          {activeTab === 'paste' && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  Toàn Văn Văn Bản (Raw Text) <span className="text-rose-400">*</span>
                </label>
                <span className="text-[11px] font-mono text-slate-500">
                  {rawText.length.toLocaleString('vi-VN')} ký tự
                </span>
              </div>
              <textarea
                rows={8}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Dán toàn văn văn bản tại đây..."
                className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3.5 text-xs font-mono text-slate-100 leading-relaxed placeholder-slate-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
          )}
        </form>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/90 px-6 py-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <FileCode className="h-4 w-4 text-brand-400" />
            <span>Phân cấp cấu trúc và trích xuất quan hệ tự động</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
            >
              Hủy
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading || !rawText.trim() || !docSlug.trim()}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-brand-950 hover:from-brand-500 hover:to-brand-600 transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                  <span>Đang bóc tách AST &amp; CPHC...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Bóc Tách &amp; Lưu Vào Staging</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
