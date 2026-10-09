import React, { useEffect, useMemo, useState } from 'react';
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
} from 'lucide-react';
import { GraphVisualizerEdge } from '../../types/api';
import { DocumentTreeNode, DocumentTreeResponse } from '../../types/tree';
import { DocumentReaderEditor } from './DocumentReaderEditor';
import { NodeInspectorPanel } from './NodeInspectorPanel';
import { TreeOutlineExplorer } from './TreeOutlineExplorer';

interface DocumentStudioContainerProps {
  docSlug: string;
  treeData: DocumentTreeResponse | null;
  edges: GraphVisualizerEdge[];
  selectedPathProp?: string;
  onSelectPathProp?: (path: string) => void;
  onRefresh?: () => void;
}

export const DocumentStudioContainer: React.FC<DocumentStudioContainerProps> = ({
  docSlug,
  treeData,
  edges,
  selectedPathProp,
  onSelectPathProp,
}) => {
  const [selectedPath, setSelectedPath] = useState<string>(() => {
    return selectedPathProp || treeData?.root?.path || '';
  });

  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  useEffect(() => {
    if (selectedPathProp) {
      setSelectedPath(selectedPathProp);
    }
  }, [selectedPathProp]);

  const handleSelectPath = (path: string) => {
    setSelectedPath(path);
    onSelectPathProp?.(path);
  };

  const [collapsedPaths, setCollapsedPaths] = useState<Set<string>>(() => {
    const set = new Set<string>();
    function traverse(node: DocumentTreeNode, depth: number) {
      if (depth > 0 && node.children && node.children.length > 0) {
        set.add(node.path);
      }
      if (node.children) {
        node.children.forEach((c) => traverse(c, depth + 1));
      }
    }
    if (treeData?.root) traverse(treeData.root, 0);
    return set;
  });

  const handleToggleCollapse = (path: string) => {
    setCollapsedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleExpandAll = () => {
    setCollapsedPaths(new Set());
  };

  const handleCollapseAll = () => {
    const allInternalPaths = new Set<string>();
    function traverse(node: DocumentTreeNode) {
      if (node.children && node.children.length > 0) {
        allInternalPaths.add(node.path);
        node.children.forEach(traverse);
      }
    }
    if (treeData?.root) traverse(treeData.root);
    setCollapsedPaths(allInternalPaths);
  };

  // Find currently selected node in treeData
  const selectedNode = useMemo(() => {
    if (!treeData?.root || !selectedPath) return null;

    function findNode(node: DocumentTreeNode): DocumentTreeNode | null {
      if (node.path === selectedPath) return node;
      if (node.children) {
        for (const c of node.children) {
          const res = findNode(c);
          if (res) return res;
        }
      }
      return null;
    }

    return findNode(treeData.root);
  }, [treeData, selectedPath]);

  return (
    <div className="flex h-full w-full overflow-hidden bg-slate-950">
      {/* Left Pane: Tree Outline Explorer */}
      <div
        className={`${
          showLeftSidebar ? 'w-72 min-w-[240px] max-w-[340px]' : 'w-0'
        } shrink-0 h-full overflow-hidden transition-all duration-200 border-r border-slate-800 flex flex-col`}
      >
        {showLeftSidebar && (
          <TreeOutlineExplorer
            rootNode={treeData?.root || null}
            totalChunks={treeData?.total_chunks}
            totalNodes={treeData?.total_nodes}
            selectedPath={selectedPath}
            onSelectPath={handleSelectPath}
            collapsedPaths={collapsedPaths}
            onToggleCollapse={handleToggleCollapse}
            onExpandAll={handleExpandAll}
            onCollapseAll={handleCollapseAll}
          />
        )}
      </div>

      {/* Center Pane: Document Reader & Inline Editor */}
      <div className="flex-1 h-full overflow-hidden flex flex-col min-w-0">
        {/* Distraction-Free Toggle Header Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs select-none">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className="flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
              title={showLeftSidebar ? 'Thu gọn Cây Cấu Trúc' : 'Mở rộng Cây Cấu Trúc'}
            >
              {showLeftSidebar ? (
                <PanelLeftClose className="h-3.5 w-3.5" />
              ) : (
                <PanelLeftOpen className="h-3.5 w-3.5 text-brand-400" />
              )}
              <span>{showLeftSidebar ? 'Ẩn Cấu Trúc' : 'Hiện Cấu Trúc'}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                const isZen = !showLeftSidebar && !showRightSidebar;
                setShowLeftSidebar(isZen);
                setShowRightSidebar(isZen);
              }}
              className={`rounded px-2 py-0.5 text-[10px] font-semibold transition ${
                !showLeftSidebar && !showRightSidebar
                  ? 'bg-brand-900 text-brand-200 border border-brand-700'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
              title="Chế độ đọc tập trung toàn màn hình (Zen Focus Mode)"
            >
              {!showLeftSidebar && !showRightSidebar ? 'Thoát Zen' : 'Zen Mode'}
            </button>
          </div>

          <span className="text-[11px] text-slate-500 font-mono truncate px-2">
            {docSlug}
          </span>

          <button
            type="button"
            onClick={() => setShowRightSidebar(!showRightSidebar)}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
            title={showRightSidebar ? 'Thu gọn Inspector Chunk' : 'Mở rộng Inspector Chunk'}
          >
            <span>{showRightSidebar ? 'Ẩn Inspector' : 'Hiện Inspector'}</span>
            {showRightSidebar ? (
              <PanelRightClose className="h-3.5 w-3.5" />
            ) : (
              <PanelRightOpen className="h-3.5 w-3.5 text-brand-400" />
            )}
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          <DocumentReaderEditor
            rootNode={treeData?.root || null}
            selectedPath={selectedPath}
            onSelectPath={handleSelectPath}
            edges={edges}
          />
        </div>
      </div>

      {/* Right Pane: Node Inspector Panel */}
      <div
        className={`${
          showRightSidebar ? 'w-80 min-w-[280px] max-w-[380px]' : 'w-0'
        } shrink-0 h-full overflow-hidden transition-all duration-200 border-l border-slate-800 flex flex-col`}
      >
        {showRightSidebar && (
          <NodeInspectorPanel
            selectedNode={selectedNode}
            onSelectPath={handleSelectPath}
            edges={edges}
            docSlug={docSlug}
          />
        )}
      </div>
    </div>
  );
};
