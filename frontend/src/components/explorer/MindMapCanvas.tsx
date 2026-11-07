import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  FileSpreadsheet,
  FileText,
  Maximize2,
  Share2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { GraphVisualizerEdge } from '../../types/api';
import { DocumentTreeNode } from '../../types/tree';
import { naturalPathCompare } from '../../utils/sorting';

interface MindMapCanvasProps {
  rootNode: DocumentTreeNode | null;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  collapsedPaths: Set<string>;
  onToggleCollapse: (path: string) => void;
  onExpandOneLevel: () => void;
  onCollapseToChapters: () => void;
  edges: GraphVisualizerEdge[];
}

interface PositionedMindNode {
  node: DocumentTreeNode;
  depth: number;
  x: number;
  y: number;
  width: number;
  height: number;
  parentPath: string | null;
  hasChildren: boolean;
  isCollapsed: boolean;
  childCount: number;
  edgeCount: number;
}

interface MindBranchLink {
  id: string;
  sourcePath: string;
  targetPath: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  isActiveSpine: boolean;
}

const LEVEL_WIDTHS = [270, 290, 290, 300, 280];
const LEVEL_GAP_X = 344;
const NODE_HEIGHT = 54;
const LEAF_STEP_Y = 66;
const CANVAS_PAD_X = 40;
const CANVAS_PAD_Y = 48;

function getNodeWidth(depth: number): number {
  return LEVEL_WIDTHS[Math.min(depth, LEVEL_WIDTHS.length - 1)];
}

function cleanDisplayLabel(label: string, path: string): string {
  const cleaned = label.replace(/^#+\s*/, '').trim();
  if (cleaned) return cleaned;
  const lastSeg = path.split('.').pop() || path;
  return lastSeg;
}

export const MindMapCanvas: React.FC<MindMapCanvasProps> = ({
  rootNode,
  selectedPath,
  onSelectPath,
  collapsedPaths,
  onToggleCollapse,
  onExpandOneLevel,
  onCollapseToChapters,
  edges,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(0.95);
  const [pan, setPan] = useState({ x: 48, y: 48 });
  const [isDragging, setIsDragging] = useState(false);
  const dragOriginRef = useRef({ x: 0, y: 0 });
  const pointerDownPosRef = useRef({ x: 0, y: 0 });
  const didDragMoveRef = useRef(false);

  // Count graph edges per path
  const edgeCountByPath = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of edges) {
      map.set(e.source_path, (map.get(e.source_path) || 0) + 1);
      if (e.target_path) {
        map.set(e.target_path, (map.get(e.target_path) || 0) + 1);
      }
    }
    return map;
  }, [edges]);

  // Compute Mind Map Tree Layout for all visible (non-collapsed) nodes
  const { positionedNodes, branchLinks, posByPath } = useMemo(() => {
    if (!rootNode) {
      return {
        positionedNodes: [] as PositionedMindNode[],
        branchLinks: [] as MindBranchLink[],
        posByPath: new Map<string, PositionedMindNode>(),
      };
    }

    const nodes: PositionedMindNode[] = [];
    const links: MindBranchLink[] = [];
    const map = new Map<string, PositionedMindNode>();
    let currentLeafSlot = 0;

    function layoutSubtree(
      node: DocumentTreeNode,
      depth: number,
      parentPath: string | null
    ): number {
      const sortedChildren = node.children
        ? [...node.children].sort((a, b) => naturalPathCompare(a.path, b.path))
        : [];
      const hasChildren = sortedChildren.length > 0;
      const isCollapsed = collapsedPaths.has(node.path);
      const width = getNodeWidth(depth);
      const x = CANVAS_PAD_X + depth * LEVEL_GAP_X;

      let centerY: number;
      if (!hasChildren || isCollapsed) {
        centerY = CANVAS_PAD_Y + currentLeafSlot * LEAF_STEP_Y + NODE_HEIGHT / 2;
        currentLeafSlot += 1;
      } else {
        const childCenters: number[] = [];
        for (const child of sortedChildren) {
          childCenters.push(layoutSubtree(child, depth + 1, node.path));
        }
        centerY =
          (childCenters[0] + childCenters[childCenters.length - 1]) / 2;
      }

      const y = centerY - NODE_HEIGHT / 2;
      const positioned: PositionedMindNode = {
        node,
        depth,
        x,
        y,
        width,
        height: NODE_HEIGHT,
        parentPath,
        hasChildren,
        isCollapsed,
        childCount: sortedChildren.length,
        edgeCount: edgeCountByPath.get(node.path) || 0,
      };

      nodes.push(positioned);
      map.set(node.path, positioned);
      return centerY;
    }

    layoutSubtree(rootNode, 0, null);

    for (const item of nodes) {
      if (!item.parentPath) continue;
      const parent = map.get(item.parentPath);
      if (!parent) continue;

      const isActiveSpine =
        Boolean(selectedPath) &&
        (selectedPath === item.node.path ||
          selectedPath.startsWith(`${item.node.path}.`)) &&
        (selectedPath === parent.node.path ||
          selectedPath.startsWith(`${parent.node.path}.`));

      links.push({
        id: `${parent.node.path}->${item.node.path}`,
        sourcePath: parent.node.path,
        targetPath: item.node.path,
        x1: parent.x + parent.width,
        y1: parent.y + parent.height / 2,
        x2: item.x,
        y2: item.y + item.height / 2,
        isActiveSpine,
      });
    }

    return { positionedNodes: nodes, branchLinks: links, posByPath: map };
  }, [rootNode, collapsedPaths, edgeCountByPath, selectedPath]);

  // Center camera smoothly on root or selected node when changed externally
  const centerOnNode = useCallback(
    (targetPath: string, targetZoom?: number) => {
      const el = containerRef.current;
      const pos = posByPath.get(targetPath);
      if (!el || !pos) return;
      const rect = el.getBoundingClientRect();
      const z = targetZoom ?? zoom;
      const nodeCenterX = pos.x + pos.width / 2;
      const nodeCenterY = pos.y + pos.height / 2;
      setPan({
        x: Math.round(rect.width * 0.36 - nodeCenterX * z),
        y: Math.round(rect.height * 0.5 - nodeCenterY * z),
      });
    },
    [posByPath, zoom]
  );

  // Reset camera when switching documents so top of visible tree and root are immediately in view
  const lastRootPathRef = useRef<string>('');
  useEffect(() => {
    if (!rootNode) return;
    if (lastRootPathRef.current !== rootNode.path) {
      lastRootPathRef.current = rootNode.path;
      const rootPos = posByPath.get(rootNode.path);
      const el = containerRef.current;
      if (rootPos && el) {
        const rect = el.getBoundingClientRect();
        const initialZoom = 0.9;
        setZoom(initialZoom);
        const targetCenterY = Math.min(rootPos.y + rootPos.height / 2, rect.height * 0.45);
        setPan({
          x: 32,
          y: Math.max(24, Math.round(rect.height * 0.45 - targetCenterY * initialZoom)),
        });
      }
    }
  }, [rootNode, posByPath]);

  // Pan to selected node whenever selection changes
  const prevSelectedRef = useRef<string>('');
  useEffect(() => {
    if (!selectedPath || selectedPath === prevSelectedRef.current) return;
    prevSelectedRef.current = selectedPath;
    if (rootNode && selectedPath === rootNode.path) return;
    centerOnNode(selectedPath);
  }, [selectedPath, rootNode, centerOnNode]);

  // Non-passive wheel handler for trackpad panning & Ctrl+Wheel zooming
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const factor = e.deltaY < 0 ? 0.08 : -0.08;
        setZoom((prev) => Math.min(1.8, Math.max(0.35, Number((prev + factor).toFixed(2)))));
      } else {
        setPan((prev) => ({
          x: prev.x - e.deltaX,
          y: prev.y - e.deltaY,
        }));
      }
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // Interrupted-gesture cleanup for pointer drag
  useEffect(() => {
    const stopDrag = () => setIsDragging(false);
    window.addEventListener('blur', stopDrag);
    window.addEventListener('mouseup', stopDrag);
    return () => {
      window.removeEventListener('blur', stopDrag);
      window.removeEventListener('mouseup', stopDrag);
    };
  }, []);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 && e.button !== 1) return;
    const target = e.target as HTMLElement;
    if (target.closest('button')) return;
    setIsDragging(true);
    didDragMoveRef.current = false;
    pointerDownPosRef.current = { x: e.clientX, y: e.clientY };
    dragOriginRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    const dx = Math.abs(e.clientX - pointerDownPosRef.current.x);
    const dy = Math.abs(e.clientY - pointerDownPosRef.current.y);
    if (dx > 3 || dy > 3) {
      didDragMoveRef.current = true;
    }
    setPan({
      x: e.clientX - dragOriginRef.current.x,
      y: e.clientY - dragOriginRef.current.y,
    });
  };

  const handlePointerUp = () => {
    setIsDragging(false);
  };

  if (!rootNode) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-950 p-8 text-center text-sm text-slate-400">
        Chưa có dữ liệu cấu trúc cho văn bản này.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      className={`relative h-full w-full overflow-hidden bg-slate-950 select-none touch-none ${
        isDragging ? 'cursor-grabbing' : 'cursor-grab'
      }`}
    >
      {/* Subtle Dot Grid Canvas Background */}
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full opacity-25"
      >
        <defs>
          <pattern
            id="mindmap-dot-grid"
            width={28 * zoom}
            height={28 * zoom}
            patternUnits="userSpaceOnUse"
            patternTransform={`translate(${pan.x}, ${pan.y})`}
          >
            <circle cx="1.5" cy="1.5" r="1" fill="currentColor" className="text-slate-500" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#mindmap-dot-grid)" />
      </svg>

      {/* Transformed Mind Map Layer */}
      <div
        className="pointer-events-none absolute inset-0 origin-top-left"
        style={{
          transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})`,
        }}
      >
        {/* SVG Branch Connectors */}
        <svg
          aria-hidden="true"
          className="pointer-events-none overflow-visible"
          style={{ width: 1, height: 1 }}
        >
          {branchLinks.map((link) => {
            const dx = Math.max(40, (link.x2 - link.x1) * 0.5);
            const d = `M ${link.x1} ${link.y1} C ${link.x1 + dx} ${link.y1}, ${
              link.x2 - dx
            } ${link.y2}, ${link.x2} ${link.y2}`;
            return (
              <path
                key={link.id}
                d={d}
                fill="none"
                stroke={link.isActiveSpine ? '#10b981' : '#64748b'}
                strokeOpacity={link.isActiveSpine ? 0.9 : 0.35}
                strokeWidth={link.isActiveSpine ? 2.25 : 1.5}
              />
            );
          })}
        </svg>

        {/* Mind Map Nodes */}
        {positionedNodes.map((item) => {
          const {
            node,
            depth,
            x,
            y,
            width,
            height,
            hasChildren,
            isCollapsed,
            childCount,
            edgeCount,
          } = item;
          const isSelected = selectedPath === node.path;
          const isInActiveBranch =
            Boolean(selectedPath) &&
            selectedPath !== node.path &&
            selectedPath.startsWith(`${node.path}.`);
          const isRoot = depth === 0;
          const isTable = Boolean(node.metadata?.is_table) || node.node_type === 'TABLE';
          const displayLabel = cleanDisplayLabel(node.label, node.path);

          return (
            <div
              key={node.path}
              style={{
                transform: `translate3d(${x}px, ${y}px, 0)`,
                width: `${width}px`,
                height: `${height}px`,
              }}
              className="pointer-events-auto absolute top-0 left-0 flex items-center"
            >
              {/* Main Node Interactive Button */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (didDragMoveRef.current) return;
                  if (hasChildren && isSelected && !isCollapsed && depth > 0) {
                    onToggleCollapse(node.path);
                    return;
                  }
                  onSelectPath(node.path);
                }}
                className={`group flex h-full w-full items-center justify-between gap-2 rounded-2xl border px-3.5 text-left transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
                  isSelected
                    ? 'border-brand-500 bg-brand-950/90 text-slate-100 shadow-md ring-2 ring-brand-500/25'
                    : isRoot
                    ? 'border-slate-700 bg-slate-900 text-slate-100 shadow-sm hover:border-brand-500/60'
                    : isInActiveBranch
                    ? 'border-brand-500/50 bg-slate-900/95 text-slate-100 hover:border-brand-500'
                    : 'border-slate-800 bg-slate-900/85 text-slate-200 hover:border-slate-600 hover:bg-slate-900'
                }`}
              >
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg ${
                      isSelected || isRoot
                        ? 'bg-brand-600 text-white'
                        : isTable
                        ? 'bg-emerald-950 text-emerald-300'
                        : 'bg-slate-800 text-slate-400 group-hover:text-slate-200'
                    }`}
                  >
                    {isTable ? (
                      <FileSpreadsheet className="h-3.5 w-3.5" />
                    ) : (
                      <FileText className="h-3.5 w-3.5" />
                    )}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div
                      className={`truncate leading-snug ${
                        isRoot
                          ? 'text-xs font-semibold'
                          : depth === 1
                          ? 'text-xs font-semibold'
                          : 'text-xs font-medium'
                      }`}
                    >
                      {displayLabel}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-[10px] text-slate-400">
                      {node.start_line > 0 && (
                        <span className="font-mono tabular-nums">
                          Dòng {node.start_line}–{node.end_line}
                        </span>
                      )}
                      {edgeCount > 0 && (
                        <span className="inline-flex items-center gap-0.5 text-brand-400 font-medium">
                          <Share2 className="h-2.5 w-2.5" />
                          {edgeCount}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Branch Expand/Collapse Pill */}
                {hasChildren && (
                  <span
                    role="button"
                    tabIndex={0}
                    aria-label={
                      isCollapsed
                        ? `Mở ${childCount} mục con của ${displayLabel}`
                        : `Thu gọn nhánh ${displayLabel}`
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      if (didDragMoveRef.current) return;
                      onToggleCollapse(node.path);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        onToggleCollapse(node.path);
                      }
                    }}
                    className={`ml-1 inline-flex shrink-0 items-center gap-0.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold tabular-nums transition-colors ${
                      isCollapsed
                        ? 'border-brand-500/40 bg-brand-950/80 text-brand-300 hover:bg-brand-900'
                        : 'border-slate-700 bg-slate-800/90 text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    <span>{childCount}</span>
                    <ChevronRight
                      className={`h-3 w-3 transition-transform duration-150 ${
                        isCollapsed ? '' : 'rotate-90'
                      }`}
                    />
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Bottom-Left Floating Mind Map Controls */}
      <div className="absolute bottom-5 left-5 z-20 flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-900/95 p-1 shadow-lg backdrop-blur-md">
        <button
          type="button"
          onClick={onCollapseToChapters}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Thu gọn về cấp Chương"
        >
          <ChevronsDownUp className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Thu gọn nhánh</span>
        </button>

        <button
          type="button"
          onClick={onExpandOneLevel}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Mở thêm 1 cấp nhánh"
        >
          <ChevronsUpDown className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Mở thêm cấp</span>
        </button>

        <div className="mx-1 h-4 w-px bg-slate-800" />

        <button
          type="button"
          onClick={() =>
            setZoom((z) => Math.max(0.35, Number((z - 0.15).toFixed(2))))
          }
          aria-label="Thu nhỏ sơ đồ"
          className="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Thu nhỏ"
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </button>

        <span className="min-w-[3.25rem] text-center font-mono text-[11px] font-medium tabular-nums text-slate-400">
          {Math.round(zoom * 100)}%
        </span>

        <button
          type="button"
          onClick={() =>
            setZoom((z) => Math.min(1.8, Number((z + 0.15).toFixed(2))))
          }
          aria-label="Phóng to sơ đồ"
          className="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Phóng to"
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </button>

        <button
          type="button"
          onClick={() => {
            const target = selectedPath || rootNode.path;
            setZoom(0.95);
            centerOnNode(target, 0.95);
          }}
          aria-label="Căn giữa lại sơ đồ"
          className="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 hover:text-slate-100 transition-colors"
          title="Căn giữa góc nhìn"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
