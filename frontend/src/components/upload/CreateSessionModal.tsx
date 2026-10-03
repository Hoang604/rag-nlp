import React, { useRef, useState } from 'react';
import {
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  Loader2,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react';
import { api } from '../../services/api';
import { INGESTION_STAGES } from '../../types/ingestion';
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

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileSize, setSelectedFileSize] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  // Auto-extract doc_slug and title from filename
  const autoInferMetadataFromFileName = (fileName: string) => {
    const baseName = fileName.replace(/\.[^/.]+$/, '').trim();
    setSelectedFileName(fileName);

    const inferredSlug = baseName
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9_]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '');

    if (!docSlug) setDocSlug(inferredSlug || 'document');
    if (!docTitle) setDocTitle(`Tài liệu: ${baseName}`);
  };

  const handleSelectedFile = (file: File) => {
    setSelectedFile(file);
    setSelectedFileSize(`${(file.size / 1024).toFixed(1)} KB`);
    autoInferMetadataFromFileName(file.name);

    // If it's a plain text/markdown file, we can optionally preview its text length
    if (file.type.startsWith('text/') || file.name.endsWith('.md') || file.name.endsWith('.txt')) {
      file.text().then((text) => {
        setRawText(text);
      }).catch(() => {
        // Non-fatal if text preview fails
      });
    } else {
      setRawText('');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanSlug = docSlug.trim();
    if (!cleanSlug) {
      error('Thiếu thông tin', 'Vui lòng nhập định danh tài liệu (doc_slug).');
      return;
    }

    if (activeTab === 'upload' && !selectedFile) {
      error('Thiếu tệp tin', 'Vui lòng chọn hoặc kéo thả một tệp tin tài liệu.');
      return;
    }

    if (activeTab === 'paste' && !rawText.trim()) {
      error('Thiếu nội dung', 'Vui lòng dán nội dung văn bản tài liệu.');
      return;
    }

    setLoading(true);

    try {
      let createdSession;
      if (activeTab === 'upload' && selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('doc_slug', cleanSlug);
        formData.append('title', docTitle.trim() || cleanSlug);

        createdSession = await api.uploadDocumentFile(formData);
      } else {
        createdSession = await api.createSessionRaw({
          doc_slug: cleanSlug,
          title: docTitle.trim() || cleanSlug,
          raw_text: rawText,
        });
      }

      const chunkCount = createdSession.chunks?.length ?? 0;
      const edgeCount = createdSession.edges?.length ?? 0;
      const tableCount = createdSession.chunks?.filter(c => c.metadata?.is_table).length ?? 0;

      success(
        'Bóc tách AST hoàn tất!',
        `Tạo phiên '${createdSession.doc_slug}': ${chunkCount} chunks, ${tableCount} bảng biểu, ${edgeCount} quan hệ genesis (100% precision).`
      );
      await onSuccess(createdSession.doc_slug);
      onClose();
    } catch (err) {
      error('Lỗi khởi tạo phiên Staging', err instanceof Error ? err.message : 'Lỗi hệ thống');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600/30 to-brand-400/10 text-brand-400 border border-brand-500/30 shadow-inner">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <span>Nạp Tài Liệu &amp; Bóc Tách AST Phân Cấp</span>
                <span className="rounded bg-brand-950 px-2 py-0.5 text-[10px] font-semibold text-brand-300 border border-brand-800">
                  Universal Parser
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Tự động bóc tách cấu trúc ltree H1..H6, bảo toàn bảng biểu và trích xuất quan hệ 100% precision
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mode Tabs */}
        <div className="flex border-b border-slate-800 bg-slate-950/70 px-6 pt-3">
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            disabled={loading}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
              activeTab === 'upload'
                ? 'border-brand-500 text-brand-300 bg-brand-950/20 rounded-t-lg'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <UploadCloud className="h-4 w-4" />
            <span>Kéo Thả Tệp Tin (.pdf, .docx, .md, .txt, .html)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('paste')}
            disabled={loading}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
              activeTab === 'paste'
                ? 'border-brand-500 text-brand-300 bg-brand-950/20 rounded-t-lg'
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
                Định Danh Tài Liệu (doc_slug) <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={docSlug}
                onChange={(e) => setDocSlug(e.target.value)}
                placeholder="ví dụ: system-architecture hoặc user-manual"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Tiêu Đề Hiển Thị
              </label>
              <input
                type="text"
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="ví dụ: Tài liệu Đặc tả Hệ thống Phân tán"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs font-medium text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                disabled={loading}
              />
            </div>
          </div>

          {/* Upload Dropzone Tab */}
          {activeTab === 'upload' && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Tệp Tin Tài Liệu Đầu Vào
              </label>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => !loading && fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-7 text-center transition ${
                  loading ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
                } ${
                  isDragging
                    ? 'border-brand-400 bg-brand-950/40 scale-[0.99]'
                    : selectedFileName
                    ? 'border-emerald-600/70 bg-emerald-950/20'
                    : 'border-slate-700 bg-slate-950/60 hover:border-slate-500 hover:bg-slate-950'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm,.json"
                  onChange={handleFileChange}
                  className="hidden"
                  disabled={loading}
                />

                {selectedFileName ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="rounded-full bg-emerald-900/40 p-3 text-emerald-400 border border-emerald-700/60 shadow-lg">
                      <CheckCircle2 className="h-6 w-6" />
                    </div>
                    <span className="font-semibold text-xs text-slate-100">
                      {selectedFileName}
                    </span>
                    <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                      <span>{selectedFileSize}</span>
                      {rawText && (
                        <span>• {rawText.length.toLocaleString('vi-VN')} ký tự text</span>
                      )}
                    </div>
                    <p className="text-[11px] text-brand-400 hover:underline mt-1">
                      Bấm để chọn tệp tin khác
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2.5">
                    <div className="rounded-full bg-slate-900 p-3 text-slate-400 border border-slate-800 shadow">
                      <UploadCloud className="h-6 w-6 text-brand-400" />
                    </div>
                    <p className="text-xs font-semibold text-slate-200">
                      Kéo thả tệp tin vào đây hoặc <span className="text-brand-400 underline">bấm để duyệt</span>
                    </p>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px]">PDF</span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px]">DOCX</span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px]">Markdown</span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px]">HTML</span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px]">Plaintext</span>
                    </div>
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
                  Nội Dung Toàn Văn (Raw Text) <span className="text-rose-400">*</span>
                </label>
                <span className="text-[11px] font-mono text-slate-500">
                  {rawText.length.toLocaleString('vi-VN')} ký tự
                </span>
              </div>
              <textarea
                rows={8}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Dán nội dung toàn văn tài liệu Markdown hoặc plain text tại đây..."
                className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3.5 text-xs font-mono text-slate-100 leading-relaxed placeholder-slate-600 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                disabled={loading}
              />
            </div>
          )}

          {/* Real-time Ingestion Processing Indicator */}
          {loading && (
            <div className="rounded-xl border border-brand-500/30 bg-brand-950/40 p-4 space-y-3">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-brand-400 shrink-0" />
                <div>
                  <span className="text-xs font-bold text-brand-200 block">
                    Đang bóc tách AST &amp; khởi tạo Staging Session...
                  </span>
                  <span className="text-[11px] text-slate-400 block">
                    Hệ thống đang chuẩn hóa cấu trúc ltree, bảo toàn bảng biểu và trích xuất quan hệ 100% precision
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-brand-900/40">
                {INGESTION_STAGES.map((s) => (
                  <div key={s.stage} className="flex items-center gap-2 text-[11px] text-slate-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse" />
                    <span className="font-medium text-slate-300">{s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </form>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/90 px-6 py-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <FileSpreadsheet className="h-4 w-4 text-indigo-400" />
            <span>Bảo toàn 100% bảng biểu &amp; liên kết đồ thị chính xác</span>
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
              disabled={
                loading ||
                !docSlug.trim() ||
                (activeTab === 'upload' && !selectedFile) ||
                (activeTab === 'paste' && !rawText.trim())
              }
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-brand-950 hover:from-brand-500 hover:to-brand-600 transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                  <span>Đang xử lý AST...</span>
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
