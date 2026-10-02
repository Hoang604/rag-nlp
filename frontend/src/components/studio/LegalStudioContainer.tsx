import React, { useMemo, useState } from 'react';
import { CreateEdgePayload } from '../../types/api';
import { StagingDocumentSession } from '../../types/staging';
import { DocumentTreeNode, DocumentTreeResponse } from '../../types/tree';
import { EdgeEditorModal } from '../graph/EdgeEditorModal';
import { DocumentReaderEditor } from './DocumentReaderEditor';
import { NodeInspectorPanel } from './NodeInspectorPanel';
import { TreeOutlineExplorer } from './TreeOutlineExplorer';

interface LegalStudioContainerProps {
  session: StagingDocumentSession;
  treeData: DocumentTreeResponse | null;
  onEditChunk: (node: DocumentTreeNode) => void;
  onDeleteChunk: (path: string) => void;
  onAddChildChunk: (parentPath: string) => void;
  onAddEdge: (edge: CreateEdgePayload) => Promise<boolean>;
  onToggleFinalizeChunk?: (node: DocumentTreeNode) => Promise<boolean | void>;
}

export const LegalStudioContainer: React.FC<LegalStudioContainerProps> = ({
  session,
  treeData,
  onEditChunk,
  onDeleteChunk,
  onAddChildChunk,
  onAddEdge,
  onToggleFinalizeChunk,
}) => {
  const [selectedPath, setSelectedPath] = useState<string>(() => {
    return treeData?.root?.path || '';
  });

  const [collapsedPaths, setCollapsedPaths] = useState<Set<string>>(() => {
    // Collect all paths that have depth > 1 to collapse by default for instant performance
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

  const [isEdgeModalOpen, setIsEdgeModalOpen] = useState(false);
  const [edgeModalSourcePath, setEdgeModalSourcePath] = useState<string | undefined>(undefined);

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
      {/* Left Pane: Tree Outline Explorer (280px) */}
      <div className="w-72 shrink-0 h-full overflow-hidden">
        <TreeOutlineExplorer
          rootNode={treeData?.root || null}
          totalFinalized={treeData?.total_finalized}
          totalPending={treeData?.total_pending}
          progressPercent={treeData?.progress_percent}
          selectedPath={selectedPath}
          onSelectPath={setSelectedPath}
          collapsedPaths={collapsedPaths}
          onToggleCollapse={handleToggleCollapse}
          onExpandAll={handleExpandAll}
          onCollapseAll={handleCollapseAll}
        />
      </div>

      {/* Center Pane: Document Reader & Inline Editor (Flex-1) */}
      <div className="flex-1 h-full overflow-hidden">
        <DocumentReaderEditor
          rootNode={treeData?.root || null}
          selectedPath={selectedPath}
          onSelectPath={setSelectedPath}
          onEditNode={onEditChunk}
          onDeleteNode={onDeleteChunk}
          onAddChildNode={onAddChildChunk}
          edges={session.edges}
        />
      </div>

      {/* Right Pane: Node Inspector Panel (320px) */}
      <div className="w-80 shrink-0 h-full overflow-hidden">
        <NodeInspectorPanel
          selectedNode={selectedNode}
          onEditNode={onEditChunk}
          onDeleteNode={onDeleteChunk}
          onAddChildNode={onAddChildChunk}
          onOpenAddEdge={(src) => {
            setEdgeModalSourcePath(src);
            setIsEdgeModalOpen(true);
          }}
          onToggleFinalize={onToggleFinalizeChunk}
          edges={session.edges}
        />
      </div>

      {/* Add Edge Modal */}
      <EdgeEditorModal
        isOpen={isEdgeModalOpen}
        onClose={() => setIsEdgeModalOpen(false)}
        onAddEdge={onAddEdge}
        initialSourcePath={edgeModalSourcePath}
      />
    </div>
  );
};
