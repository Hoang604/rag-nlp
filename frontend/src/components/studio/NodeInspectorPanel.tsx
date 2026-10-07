import React, { useState } from 'react';
import {
  Compass,
  Copy,
  FileCode,
  FileSpreadsheet,
  FileText,
  Share2,
  Sliders,
  X,
} from 'lucide-react';
import { useToast } from '../toast/ToastContext';
import { StagingEdge } from '../../types/staging';
import { DocumentTreeNode } from '../../types/tree';
import { getNodeTypeColor } from '../../utils/ltree';
import { GraphTraversalModal } from '../graph/GraphTraversalModal';

interface NodeInspectorPanelProps {
  selectedNode: DocumentTreeNode | null;
  onClose?: () => void;
  onSelectPath?: (path: string) => void;
  edges: StagingEdge[];
  docSlug?: string;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  selectedNode,
  onClose,
  onSelectPath,
  edges,
  docSlug,
}) => {
  const { success } = useToast();
  const [isTraversalOpen, setIsTraversalOpen] = useState(false);

  if (!selectedNode) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-6 text-center text-xs text-slate-500 border-l border-slate-800 bg-slate-950">
        <Sliders className="h-8 w-8 text-slate-600 mb-2" />
        <p className="font-semibold text-slate-400">Chưa chọn chunk</p>
        <p className="mt-1 text-[11px]">
          Bấm vào bất kỳ chunk nào ở danh sách hoặc toàn văn để xem chi tiết
        </p>
      </div>
    );
  }

  const colors = getNodeTypeColor(selectedNode.node_type);

  // Find all relational edges involving this node
  const relatedEdges = edges.filter(
    (e) =>
      e.source_path === selectedNode.path || e.target_path === selectedNode.path
  );

  const copyToClipboard = (text: string, label: string) => {
    void navigator.clipboard.writeText(text);
    success('Đã sao chép', `Đã sao chép ${label} vào clipboard.`);
  };

  return (
    <div className="flex h-full w-full flex-col border-l border-slate-800 bg-slate-950 overflow-y-auto">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4 py-3">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-brand-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Inspector Chunk
          </span>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Main Inspector Body */}
      <div className="p-4 space-y-5 text-xs">
        {/* Title & Badge */}
        <div>
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span
              className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase ${colors.badge}`}
            >
              {selectedNode.node_type}
            </span>
            <span
              className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                selectedNode.review_status === 'REVIEWED'
                  ? 'border-emerald-600/60 bg-emerald-950/80 text-emerald-300'
                  : 'border-amber-600/60 bg-amber-950/80 text-amber-300'
              }`}
            >
              {selectedNode.review_status === 'REVIEWED' ? 'ĐÃ RÀ SOÁT' : 'CHỜ RÀ SOÁT'}
            </span>
            {selectedNode.finalization_state && (
              <span
                className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                  selectedNode.finalization_state === 'FINALIZED_FULLY_LINKED'
                    ? 'border-cyan-600/60 bg-cyan-950/80 text-cyan-300'
                    : selectedNode.finalization_state === 'FINALIZED_SELF_CONTAINED'
                    ? 'border-emerald-600/60 bg-emerald-950/80 text-emerald-300'
                    : 'border-amber-600/60 bg-amber-950/80 text-amber-300'
                }`}
              >
                {selectedNode.finalization_state === 'FINALIZED_FULLY_LINKED'
                  ? 'FULLY LINKED'
                  : selectedNode.finalization_state === 'FINALIZED_SELF_CONTAINED'
                  ? 'SELF CONTAINED'
                  : 'UNFINALIZED'}
              </span>
            )}
            {Boolean(selectedNode.metadata?.is_table) && (
              <span className="rounded border border-indigo-700 bg-indigo-950/80 px-1.5 py-0.5 text-[10px] font-bold uppercase text-indigo-300">
                BẢNG BIỂU
              </span>
            )}
            <span className="font-bold text-sm text-slate-100">
              {selectedNode.label}
            </span>
          </div>

          <div className="flex items-center justify-between rounded-lg bg-slate-900/80 p-2 border border-slate-800">
            <span className="font-mono text-[11px] text-brand-300 font-semibold truncate">
              {selectedNode.path}
            </span>
            <button
              onClick={() => copyToClipboard(selectedNode.path, 'LTREE Path')}
              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
              title="Sao chép path"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Verbatim Text Section */}
        {selectedNode.verbatim_text && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Nội Dung Nguyên Văn
              </span>
              <button
                onClick={() =>
                  copyToClipboard(selectedNode.verbatim_text, 'Nội dung nguyên văn')
                }
                className="text-[10px] text-brand-400 hover:underline flex items-center gap-1"
              >
                <Copy className="h-3 w-3" />
                <span>Sao chép</span>
              </button>
            </div>
            <div className="rounded-lg bg-slate-950 p-3 border border-slate-800 font-mono text-slate-200 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {selectedNode.verbatim_text}
            </div>
          </div>
        )}

        {/* Contextualized Text */}
        {selectedNode.contextualized_text && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-semibold text-brand-400 uppercase tracking-wider flex items-center gap-1">
                <FileText className="h-3.5 w-3.5" />
                <span>Văn Cảnh Ngữ Cảnh Tổng Hợp</span>
              </span>
              <button
                onClick={() =>
                  copyToClipboard(selectedNode.contextualized_text, 'Văn cảnh ngữ cảnh')
                }
                className="text-[10px] text-brand-400 hover:underline flex items-center gap-1"
              >
                <Copy className="h-3 w-3" />
                <span>Sao chép</span>
              </button>
            </div>
            <div className="rounded-lg bg-slate-950 p-3 border border-slate-800 font-mono text-slate-300 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {selectedNode.contextualized_text}
            </div>
          </div>
        )}

        {/* Table Block Details */}
        {Boolean(selectedNode.metadata?.is_table) && (
          <div className="rounded-lg bg-indigo-950/40 p-3 border border-indigo-800/60 space-y-2">
            <div className="flex items-center gap-2 text-indigo-300 font-semibold text-xs">
              <FileSpreadsheet className="h-4 w-4" />
              <span>Khối Bảng Biểu Nguyên Vẹn (Table Block)</span>
            </div>
            {Boolean(selectedNode.metadata?.table_summary) && (
              <p className="text-[11px] text-slate-300 italic">
                {String(selectedNode.metadata.table_summary)}
              </p>
            )}
            <div className="flex items-center gap-3 text-[10px] font-mono text-indigo-200">
              {selectedNode.metadata?.row_count !== undefined && (
                <span>Số hàng: {String(selectedNode.metadata.row_count)}</span>
              )}
              {selectedNode.metadata?.col_count !== undefined && (
                <span>Số cột: {String(selectedNode.metadata.col_count)}</span>
              )}
            </div>
            {Array.isArray(selectedNode.metadata?.headers) && selectedNode.metadata.headers.length > 0 && (
              <div className="text-[10px] text-slate-400">
                <span className="font-semibold text-slate-300">Cột: </span>
                <span>{(selectedNode.metadata.headers as string[]).join(', ')}</span>
              </div>
            )}
          </div>
        )}

        {/* Line Span & Node Type Section */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-slate-900/60 p-2.5 border border-slate-800">
            <span className="text-[10px] text-slate-500 font-semibold block mb-0.5">
              Vị trí dòng nguồn:
            </span>
            <span className="font-mono font-bold text-slate-200">
              Dòng {selectedNode.start_line} - {selectedNode.end_line}
            </span>
          </div>

          <div className="rounded-lg bg-slate-900/60 p-2.5 border border-slate-800">
            <span className="text-[10px] text-slate-500 font-semibold block mb-0.5">
              Nút AST:
            </span>
            <span className="font-mono font-bold text-slate-200">
              {selectedNode.node_type}
            </span>
          </div>
        </div>

        {/* Relational Knowledge Graph Connections */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Share2 className="h-3.5 w-3.5 text-blue-400" />
              <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
                Quan Hệ Đồ Thị ({relatedEdges.length})
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsTraversalOpen(true)}
              className="text-[10px] font-semibold text-cyan-400 hover:underline flex items-center gap-0.5"
              title="Duyệt đồ thị đa tầng BFS"
            >
              <Compass className="h-3 w-3" />
              <span>Duyệt đa tầng</span>
            </button>
          </div>

          {relatedEdges.length === 0 ? (
            <div className="rounded-lg bg-slate-900/40 p-3 text-center text-[11px] text-slate-500 border border-slate-800/80">
              Chưa có liên kết hoặc quan hệ nào gắn với chunk này.
            </div>
          ) : (
            <div className="space-y-2">
              {relatedEdges.map((e, idx) => (
                <div
                  key={idx}
                  className="rounded-lg bg-slate-900/80 p-2.5 border border-slate-800 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="rounded bg-blue-950 px-1.5 py-0.5 text-[9px] font-bold text-blue-300 border border-blue-800">
                      {e.relation_type}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {e.source_path === selectedNode.path ? 'Xuất phát (Ra)' : 'Đích đến (Vào)'}
                    </span>
                  </div>

                  <div
                    onClick={() => {
                      const target = e.source_path === selectedNode.path ? e.target_path : e.source_path;
                      if (onSelectPath && target) onSelectPath(target);
                    }}
                    className={`font-mono text-[11px] truncate transition ${
                      onSelectPath
                        ? 'cursor-pointer text-blue-400 hover:text-blue-200 hover:underline'
                        : 'text-slate-200'
                    }`}
                    title="Bấm để chuyển tới chunk này"
                  >
                    {e.source_path === selectedNode.path
                      ? `→ ${e.target_path}`
                      : `← ${e.source_path}`}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Metadata JSON */}
        {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <FileCode className="h-3.5 w-3.5" />
              <span>Metadata Payloads</span>
            </div>
            <pre className="rounded-lg bg-slate-950 p-3 border border-slate-800 font-mono text-[10px] text-slate-300 overflow-x-auto leading-relaxed">
              {JSON.stringify(selectedNode.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Multi-Hop Traversal Modal */}
      {docSlug && selectedNode && (
        <GraphTraversalModal
          isOpen={isTraversalOpen}
          onClose={() => setIsTraversalOpen(false)}
          docSlug={docSlug}
          initialSourcePath={selectedNode.path}
          onSelectNode={onSelectPath}
        />
      )}
    </div>
  );
};
