import React, { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Filter,
  FolderTree,
  Search,
} from 'lucide-react';
import { DocumentTreeNode } from '../../types/tree';
import { getNodeTypeColor } from '../../utils/ltree';
import { naturalLegalCompare } from '../../utils/sorting';

interface TreeOutlineExplorerProps {
  rootNode: DocumentTreeNode | null;
  totalFinalized?: number;
  totalPending?: number;
  progressPercent?: number;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  collapsedPaths: Set<string>;
  onToggleCollapse: (path: string) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}

interface OutlineItemProps {
  node: DocumentTreeNode;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  collapsedPaths: Set<string>;
  onToggleCollapse: (path: string) => void;
  depth: number;
}

const OutlineItem: React.FC<OutlineItemProps> = ({
  node,
  selectedPath,
  onSelectPath,
  collapsedPaths,
  onToggleCollapse,
  depth,
}) => {
  const hasChildren = node.children && node.children.length > 0;
  const isCollapsed = collapsedPaths.has(node.path);
  const isSelected = selectedPath === node.path;
  const colors = getNodeTypeColor(node.node_type);

  return (
    <div className="select-none">
      <div
        onClick={() => onSelectPath(node.path)}
        style={{ paddingLeft: `${Math.max(8, depth * 14)}px` }}
        className={`group flex items-center gap-1.5 py-1.5 pr-2.5 rounded-lg cursor-pointer transition text-xs font-medium ${
          isSelected
            ? 'bg-brand-950/90 text-brand-200 font-semibold ring-1 ring-brand-500/40'
            : 'text-slate-300 hover:bg-slate-900/80 hover:text-slate-100'
        }`}
      >
        {/* Expand / Collapse toggle */}
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleCollapse(node.path);
            }}
            className="p-0.5 text-slate-500 hover:text-slate-200 rounded"
          >
            {isCollapsed ? (
              <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {/* Node Type Badge */}
        <span
          className={`shrink-0 rounded px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider ${colors.badge}`}
        >
          {node.node_type.substring(0, 3)}
        </span>

        {/* Status Dot Indicator */}
        <span
          className={`h-2 w-2 shrink-0 rounded-full ${
            node.review_status === 'REVIEWED'
              ? 'bg-emerald-400 ring-1 ring-emerald-500/50'
              : 'bg-amber-400 ring-1 ring-amber-500/50'
          }`}
          title={node.review_status === 'REVIEWED' ? 'Đã rà soát' : 'Chờ rà soát'}
        />

        {/* Label */}
        <span className="truncate flex-1 font-medium">{node.label}</span>

        {/* Child count if collapsed */}
        {hasChildren && isCollapsed && (
          <span className="text-[10px] text-slate-500 font-mono">
            {node.children.length}
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && !isCollapsed && (
        <div>
          {[...node.children]
            .sort((a, b) => naturalLegalCompare(a.path, b.path))
            .map((child) => (
              <OutlineItem
                key={child.path}
                node={child}
                selectedPath={selectedPath}
                onSelectPath={onSelectPath}
                collapsedPaths={collapsedPaths}
                onToggleCollapse={onToggleCollapse}
                depth={depth + 1}
              />
            ))}
        </div>
      )}
    </div>
  );
};

export const TreeOutlineExplorer: React.FC<TreeOutlineExplorerProps> = ({
  rootNode,
  totalFinalized,
  totalPending,
  progressPercent,
  selectedPath,
  onSelectPath,
  collapsedPaths,
  onToggleCollapse,
  onExpandAll,
  onCollapseAll,
}) => {
  const [searchFilter, setSearchFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const totalChunks = (totalFinalized ?? 0) + (totalPending ?? 0);

  // Filter outline nodes
  const filteredRoot = useMemo(() => {
    if (!rootNode) return null;
    if (!searchFilter && !typeFilter && !statusFilter) return rootNode;

    function filterNode(node: DocumentTreeNode): DocumentTreeNode | null {
      const matchSearch =
        !searchFilter ||
        node.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
        node.path.toLowerCase().includes(searchFilter.toLowerCase());

      const matchType =
        !typeFilter ||
        node.node_type.toUpperCase() === typeFilter.toUpperCase();

      const matchStatus =
        !statusFilter ||
        (node.review_status || 'PENDING').toUpperCase() === statusFilter.toUpperCase();

      const matchedChildren: DocumentTreeNode[] = [];
      if (node.children) {
        for (const child of node.children) {
          const res = filterNode(child);
          if (res) matchedChildren.push(res);
        }
      }

      if ((matchSearch && matchType && matchStatus) || matchedChildren.length > 0) {
        return {
          ...node,
          children: matchedChildren,
        };
      }
      return null;
    }

    return filterNode(rootNode);
  }, [rootNode, searchFilter, typeFilter, statusFilter]);

  return (
    <div className="flex h-full w-full flex-col border-r border-slate-800 bg-slate-950">
      {/* Header */}
      <div className="flex flex-col gap-2 border-b border-slate-800 bg-slate-900/80 px-3.5 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderTree className="h-4 w-4 text-brand-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Cấu Trúc
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onCollapseAll}
              title="Thu gọn tất cả"
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            >
              Thu gọn
            </button>
            <button
              type="button"
              onClick={onExpandAll}
              title="Mở rộng tất cả"
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-brand-400 hover:bg-slate-800 hover:text-brand-300"
            >
              Mở hết
            </button>
          </div>
        </div>

        {/* Visual Progress Bar and Stats */}
        {totalChunks > 0 && (
          <div className="space-y-1 pt-0.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400 font-medium">Tiến độ chốt:</span>
              <span className="font-mono font-semibold text-emerald-400">
                {totalFinalized ?? 0}/{totalChunks} ({progressPercent ?? 0}%)
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-600 to-teal-400 rounded-full transition-all duration-300"
                style={{
                  width: `${Math.min(100, Math.max(0, progressPercent ?? 0))}%`,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Quick Search & Filter */}
      <div className="border-b border-slate-800 bg-slate-900/40 p-2.5 space-y-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Tìm theo Điều, Khoản, Điểm..."
            className="w-full rounded-md border border-slate-700 bg-slate-950 py-1.5 pl-7 pr-2.5 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-1.5">
          <Filter className="h-3 w-3 text-slate-500" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[11px] text-slate-300 focus:border-brand-500 focus:outline-none"
          >
            <option value="">Tất cả phân cấp</option>
            <option value="CHAPTER">Chương (CHAPTER)</option>
            <option value="ARTICLE">Điều (ARTICLE)</option>
            <option value="CLAUSE">Khoản (CLAUSE)</option>
            <option value="POINT">Điểm (POINT)</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[11px] text-slate-300 focus:border-brand-500 focus:outline-none"
          >
            <option value="">Tất cả</option>
            <option value="PENDING">Chờ rà soát</option>
            <option value="REVIEWED">Đã rà soát</option>
          </select>
        </div>
      </div>

      {/* Outline Tree List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {!filteredRoot ? (
          <div className="p-4 text-center text-xs text-slate-500">
            Không tìm thấy mục nào khớp bộ lọc.
          </div>
        ) : (
          <OutlineItem
            node={filteredRoot}
            selectedPath={selectedPath}
            onSelectPath={onSelectPath}
            collapsedPaths={collapsedPaths}
            onToggleCollapse={onToggleCollapse}
            depth={0}
          />
        )}
      </div>
    </div>
  );
};
