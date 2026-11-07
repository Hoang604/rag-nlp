import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronRight,
  Copy,
  FileSpreadsheet,
  FileText,
  Share2,
  X,
} from 'lucide-react';
import { useToast } from '../toast/ToastContext';
import { GraphVisualizerEdge } from '../../types/api';
import { DocumentTreeNode } from '../../types/tree';
import { naturalPathCompare } from '../../utils/sorting';

interface NodeInspectorPanelProps {
  rootNode: DocumentTreeNode | null;
  selectedNode: DocumentTreeNode | null;
  onClose: () => void;
  onSelectPath: (path: string) => void;
  edges: GraphVisualizerEdge[];
}

function cleanTitle(label: string): string {
  return label.replace(/^#+\s*/, '').trim();
}

function stripDuplicateLeadingHeading(text: string, label: string): string {
  const trimmed = text.trim();
  const lines = trimmed.split('\n');
  if (lines.length === 0) return trimmed;
  const firstLineClean = lines[0].replace(/^#+\s*/, '').trim();
  const labelClean = cleanTitle(label);
  if (
    firstLineClean &&
    labelClean &&
    firstLineClean.toLowerCase() === labelClean.toLowerCase()
  ) {
    return lines.slice(1).join('\n').trim();
  }
  return trimmed;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  rootNode,
  selectedNode,
  onClose,
  onSelectPath,
  edges,
}) => {
  const { success } = useToast();

  // Build ancestor breadcrumb trail from rootNode down to selectedNode
  const breadcrumbs = useMemo(() => {
    if (!rootNode || !selectedNode) return [] as DocumentTreeNode[];
    const trail: DocumentTreeNode[] = [];

    function dfs(curr: DocumentTreeNode): boolean {
      trail.push(curr);
      if (curr.path === selectedNode?.path) return true;
      if (curr.children) {
        for (const child of curr.children) {
          if (dfs(child)) return true;
        }
      }
      trail.pop();
      return false;
    }

    dfs(rootNode);
    return trail;
  }, [rootNode, selectedNode]);

  if (!selectedNode) return null;

  const relatedEdges = edges.filter(
    (e) =>
      e.source_path === selectedNode.path || e.target_path === selectedNode.path
  );

  const sortedChildren = selectedNode.children
    ? [...selectedNode.children].sort((a, b) => naturalPathCompare(a.path, b.path))
    : [];

  const bodyMarkdown = selectedNode.verbatim_text
    ? stripDuplicateLeadingHeading(selectedNode.verbatim_text, selectedNode.label)
    : '';

  const copyToClipboard = (text: string, label: string) => {
    void navigator.clipboard.writeText(text);
    success('Đã sao chép', `Đã sao chép ${label} vào bộ nhớ tạm.`);
  };

  return (
    <aside
      aria-label="Nội dung chi tiết mục đang chọn"
      className="flex h-full w-full flex-col border-l border-slate-800 bg-slate-950 overflow-hidden"
    >
      {/* Clean Header with Breadcrumbs & Close Action */}
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-5 py-3.5">
        <div className="min-w-0 flex-1">
          {breadcrumbs.length > 1 && (
            <nav
              aria-label="Đường dẫn phân cấp"
              className="mb-1 flex flex-wrap items-center gap-1 text-xs text-slate-400"
            >
              {breadcrumbs.slice(0, -1).map((crumb, idx) => (
                <React.Fragment key={crumb.path}>
                  {idx > 0 && <ChevronRight className="h-3 w-3 shrink-0 text-slate-500" />}
                  <button
                    type="button"
                    onClick={() => onSelectPath(crumb.path)}
                    className="max-w-[180px] truncate rounded px-1 py-0.5 text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors"
                  >
                    {cleanTitle(crumb.label)}
                  </button>
                </React.Fragment>
              ))}
            </nav>
          )}

          <h2 className="text-base font-semibold leading-snug text-slate-100">
            {cleanTitle(selectedNode.label)}
          </h2>

          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            {selectedNode.start_line > 0 && (
              <span className="font-mono tabular-nums">
                Dòng {selectedNode.start_line}–{selectedNode.end_line}
              </span>
            )}
            <span aria-hidden="true">·</span>
            <button
              type="button"
              onClick={() => copyToClipboard(selectedNode.path, 'đường dẫn mục')}
              className="inline-flex max-w-full items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] text-slate-400 hover:bg-slate-900 hover:text-slate-200 transition-colors"
              title="Sao chép mã đường dẫn LTree"
            >
              <span className="truncate">{selectedNode.path}</span>
              <Copy className="h-3 w-3 shrink-0" />
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng khung đọc chi tiết"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors"
          title="Đóng khung đọc"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Scrollable Reading Canvas */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-5">
        {/* Main Provision Content */}
        {bodyMarkdown ? (
          <div>
            <div className="mb-2 flex items-center justify-end">
              <button
                type="button"
                onClick={() =>
                  copyToClipboard(selectedNode.verbatim_text, 'nội dung điều khoản')
                }
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors"
              >
                <Copy className="h-3 w-3" />
                <span>Sao chép toàn văn</span>
              </button>
            </div>
            <div className="answer-markdown text-sm leading-relaxed text-slate-100">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {bodyMarkdown}
              </ReactMarkdown>
            </div>
          </div>
        ) : (
          !sortedChildren.length && (
            <p className="text-sm text-slate-400">
              Mục này là nút phân cấp trung gian, không có đoạn văn bản riêng.
            </p>
          )
        )}

        {/* Child Provisions List (for Chapters / Sections / Articles with sub-items) */}
        {sortedChildren.length > 0 && (
          <div>
            <h3 className="mb-2.5 text-xs font-semibold text-slate-400">
              Các mục trực thuộc ({sortedChildren.length})
            </h3>
            <div className="divide-y divide-slate-800/80 rounded-xl border border-slate-800 bg-slate-900/40">
              {sortedChildren.map((child) => {
                const isTable =
                  Boolean(child.metadata?.is_table) || child.node_type === 'TABLE';
                const preview = child.verbatim_text
                  ? stripDuplicateLeadingHeading(child.verbatim_text, child.label)
                  : '';
                return (
                  <button
                    key={child.path}
                    type="button"
                    onClick={() => onSelectPath(child.path)}
                    className="group flex w-full items-start justify-between gap-3 px-3.5 py-2.5 text-left hover:bg-slate-900/90 transition-colors first:rounded-t-xl last:rounded-b-xl"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        {isTable ? (
                          <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                        ) : (
                          <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400 group-hover:text-brand-400" />
                        )}
                        <span className="truncate text-xs font-semibold text-slate-100 group-hover:text-brand-400">
                          {cleanTitle(child.label)}
                        </span>
                      </div>
                      {preview && (
                        <p className="mt-1 line-clamp-2 pl-5.5 text-xs leading-relaxed text-slate-400">
                          {preview}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5 pt-0.5 text-[11px] text-slate-400">
                      {child.children && child.children.length > 0 && (
                        <span className="rounded-full bg-slate-800 px-2 py-0.5 font-mono text-[10px] tabular-nums">
                          {child.children.length}
                        </span>
                      )}
                      <ChevronRight className="h-3.5 w-3.5 text-slate-500 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Cross-reference Graph Links (only rendered when edges exist) */}
        {relatedEdges.length > 0 && (
          <div className="pt-2 border-t border-slate-800">
            <h3 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Share2 className="h-3.5 w-3.5 text-brand-400" />
              <span>Liên kết tham chiếu ({relatedEdges.length})</span>
            </h3>
            <div className="space-y-2">
              {relatedEdges.map((e, idx) => {
                const isOutgoing = e.source_path === selectedNode.path;
                const counterpartPath = isOutgoing ? e.target_path : e.source_path;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      if (counterpartPath) onSelectPath(counterpartPath);
                    }}
                    className="flex w-full items-center justify-between gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-left text-xs hover:border-brand-500/50 hover:bg-slate-900 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-[10px] font-semibold text-brand-400">
                        {e.relation_type}
                      </span>
                      <div className="mt-0.5 truncate font-mono text-[11px] text-slate-200">
                        {isOutgoing ? `→ ${counterpartPath}` : `← ${counterpartPath}`}
                      </div>
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
