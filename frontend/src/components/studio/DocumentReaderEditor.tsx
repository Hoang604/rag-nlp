import React, { memo, useEffect, useRef } from 'react';
import {
  Edit3,
  FileText,
  Plus,
  Share2,
  Trash2,
} from 'lucide-react';
import { StagingEdge } from '../../types/staging';
import { DocumentTreeNode } from '../../types/tree';
import { getNodeTypeColor } from '../../utils/ltree';
import { naturalPathCompare } from '../../utils/sorting';

interface DocumentReaderEditorProps {
  rootNode: DocumentTreeNode | null;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  onEditNode: (node: DocumentTreeNode) => void;
  onDeleteNode: (path: string) => void;
  onAddChildNode: (parentPath: string) => void;
  edges: StagingEdge[];
}

interface RenderSectionProps {
  node: DocumentTreeNode;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  onEditNode: (node: DocumentTreeNode) => void;
  onDeleteNode: (path: string) => void;
  onAddChildNode: (parentPath: string) => void;
  edges: StagingEdge[];
  nodeRefs: React.MutableRefObject<Map<string, HTMLDivElement>>;
  depth: number;
}

const RenderSection: React.FC<RenderSectionProps> = memo(
  ({
    node,
    selectedPath,
    onSelectPath,
    onEditNode,
    onDeleteNode,
    onAddChildNode,
    edges,
    nodeRefs,
    depth,
  }) => {
    const isSelected = selectedPath === node.path;
    const colors = getNodeTypeColor(node.node_type);

    // Find all relational edges involving this node
    const relatedEdges = edges.filter(
      (e) => e.source_path === node.path || e.target_path === node.path
    );

    const isTopLevel = node.node_type === 'DOCUMENT' || depth === 0;

    return (
      <div
        ref={(el) => {
          if (el) nodeRefs.current.set(node.path, el);
          else nodeRefs.current.delete(node.path);
        }}
        id={`doc-node-${node.path.replace(/\./g, '-')}`}
        style={{ contentVisibility: 'auto', containIntrinsicSize: isTopLevel ? '140px' : '90px' }}
        onClick={(e) => {
          e.stopPropagation();
          onSelectPath(node.path);
        }}
        className={`group relative my-3 rounded-xl border transition-all duration-150 cursor-pointer ${
          isSelected
            ? 'border-brand-500 bg-brand-950/30 ring-2 ring-brand-500/30 shadow-lg'
            : isTopLevel
            ? 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
            : 'border-slate-850 bg-slate-900/40 hover:border-slate-700'
        } ${depth > 0 ? 'ml-4 sm:ml-6 pl-3 sm:pl-4 border-l-2' : 'p-5'}`}
      >
        {/* Node Heading Banner */}
        <div className="flex items-center justify-between gap-3 pb-2 mb-2 border-b border-slate-800/80">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${colors.badge}`}
            >
              {node.node_type}
            </span>

            <span
              className={`font-bold text-slate-100 ${
                node.node_type === 'DOCUMENT'
                  ? 'text-base sm:text-lg text-brand-300'
                  : depth === 1
                  ? 'text-sm sm:text-base text-purple-300'
                  : 'text-xs sm:text-sm text-slate-200'
              }`}
            >
              {node.label}
            </span>

            <span className="rounded bg-slate-950 px-2 py-0.5 font-mono text-[10px] text-slate-400 border border-slate-800">
              {node.path}
            </span>
          </div>

          {/* Quick Action Toolbar */}
          <div className="flex items-center gap-1 opacity-70 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              title="Thêm mục con"
              onClick={(e) => {
                e.stopPropagation();
                onAddChildNode(node.path);
              }}
              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-brand-300 transition"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              title="Sửa chunk"
              onClick={(e) => {
                e.stopPropagation();
                onEditNode(node);
              }}
              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-brand-300 transition"
            >
              <Edit3 className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              title="Xóa chunk"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteNode(node.path);
              }}
              className="rounded p-1 text-slate-400 hover:bg-rose-950 hover:text-rose-400 transition"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>


        {/* Verbatim text */}
        {node.verbatim_text && (
          <div className="font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap bg-slate-950/70 p-3 rounded-lg border border-slate-800/80 mb-2.5">
            {node.verbatim_text}
          </div>
        )}

        {/* Contextualized text preview */}
        {node.contextualized_text && node.contextualized_text !== node.verbatim_text && (
          <details className="text-[11px] text-slate-400 mb-2">
            <summary className="cursor-pointer hover:text-slate-200 select-none flex items-center gap-1 font-medium text-brand-400/90">
              <FileText className="h-3 w-3" />
              <span>Xem văn cảnh ngữ nghĩa tổng hợp</span>
            </summary>
            <div className="mt-1.5 rounded bg-slate-900/90 p-2.5 border border-slate-800 text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
              {node.contextualized_text}
            </div>
          </details>
        )}

        {/* Related Graph Edge Tags */}
        {relatedEdges.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <Share2 className="h-3 w-3 text-blue-400" />
            {relatedEdges.map((e, idx) => (
              <span
                key={idx}
                className="rounded bg-blue-950/80 px-2 py-0.5 text-[10px] font-mono text-blue-300 border border-blue-800"
              >
                {e.relation_type} &rarr; {e.target_path}
              </span>
            ))}
          </div>
        )}

        {/* Recursive Children Rendering */}
        {node.children && node.children.length > 0 && (
          <div className="mt-2 space-y-2">
            {[...node.children]
              .sort((a, b) => naturalPathCompare(a.path, b.path))
              .map((child) => (
                <RenderSection
                  key={child.path}
                  node={child}
                  selectedPath={selectedPath}
                  onSelectPath={onSelectPath}
                  onEditNode={onEditNode}
                  onDeleteNode={onDeleteNode}
                  onAddChildNode={onAddChildNode}
                  edges={edges}
                  nodeRefs={nodeRefs}
                  depth={depth + 1}
                />
              ))}
          </div>
        )}
      </div>
    );
  }
);

RenderSection.displayName = 'RenderSection';

export const DocumentReaderEditor: React.FC<DocumentReaderEditorProps> = ({
  rootNode,
  selectedPath,
  onSelectPath,
  onEditNode,
  onDeleteNode,
  onAddChildNode,
  edges,
}) => {
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Auto-scroll center pane to selected node
  useEffect(() => {
    if (selectedPath) {
      const el = nodeRefs.current.get(selectedPath);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [selectedPath]);

  if (!rootNode) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8 text-center text-xs text-slate-500">
        Chưa có dữ liệu chunk trong phiên này.
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-y-auto bg-slate-950 p-6 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <RenderSection
          node={rootNode}
          selectedPath={selectedPath}
          onSelectPath={onSelectPath}
          onEditNode={onEditNode}
          onDeleteNode={onDeleteNode}
          onAddChildNode={onAddChildNode}
          edges={edges}
          nodeRefs={nodeRefs}
          depth={0}
        />
      </div>
    </div>
  );
};
