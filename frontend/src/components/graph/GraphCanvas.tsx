import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Info,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { StagingChunk, StagingDocumentSession, StagingEdge } from '../../types/staging';

interface GraphCanvasProps {
  session: StagingDocumentSession;
  onSelectNode?: (path: string) => void;
}

interface GraphNodePos {
  path: string;
  label: string;
  nodeType?: string;
  reviewStatus?: string;
  isExternal?: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  inDegree: number;
  outDegree: number;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  session,
  onSelectNode,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 40, y: 40 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPanPos, setStartPanPos] = useState({ x: 0, y: 0 });

  const [selectedEdge, setSelectedEdge] = useState<StagingEdge | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Attach native non-passive wheel listener on Graph Canvas
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (e.ctrlKey || e.metaKey) {
        const delta = e.deltaY < 0 ? 0.08 : -0.08;
        setZoomLevel((prev) => Math.min(2.5, Math.max(0.2, prev + delta)));
      } else {
        setPanOffset((prev) => ({
          x: prev.x - e.deltaX,
          y: prev.y - e.deltaY,
        }));
      }
    };

    el.addEventListener('wheel', handleWheelNative, { passive: false });
    return () => {
      el.removeEventListener('wheel', handleWheelNative);
    };
  }, []);

  // F-7: Extract all unique nodes from session.chunks as well as session.edges so isolated nodes are fully visible
  const { nodes, edgesWithPos } = useMemo(() => {
    const nodeSet = new Set<string>();
    const inDegrees: Record<string, number> = {};
    const outDegrees: Record<string, number> = {};
    const chunkMap = new Map<string, StagingChunk>();

    for (const c of session.chunks || []) {
      chunkMap.set(c.path, c);
      nodeSet.add(c.path);
    }

    for (const e of session.edges) {
      nodeSet.add(e.source_path);
      outDegrees[e.source_path] = (outDegrees[e.source_path] || 0) + 1;
      if (e.target_path) {
        nodeSet.add(e.target_path);
        inDegrees[e.target_path] = (inDegrees[e.target_path] || 0) + 1;
      }
    }

    // Hierarchical DAG / Tree layout: group by ltree depth level
    const sortedNodePaths = Array.from(nodeSet).sort();
    const nodePositions: GraphNodePos[] = [];
    const nMap = new Map<string, GraphNodePos>();

    const levelMap = new Map<number, string[]>();
    sortedNodePaths.forEach((path) => {
      const depth = Math.max(0, path.split('.').length - 1);
      if (!levelMap.has(depth)) {
        levelMap.set(depth, []);
      }
      levelMap.get(depth)!.push(path);
    });

    const levelSpacing = 280;
    const rowSpacing = 110;

    levelMap.forEach((pathsInLevel, level) => {
      pathsInLevel.forEach((path, rowIdx) => {
        const x = 50 + level * levelSpacing;
        const y = 50 + rowIdx * rowSpacing;

        const chunk = chunkMap.get(path);
        const isExternal = !chunk;
        const nodeType = isExternal
          ? 'NGOẠI VI'
          : (chunk?.metadata?.node_type as string) ||
            (chunk as { node_type?: string })?.node_type ||
            (chunk?.metadata?.is_table ? 'TABLE' : 'PARAGRAPH');
        const reviewStatus = isExternal ? undefined : (chunk?.review_status || 'PENDING');

        const nodeObj: GraphNodePos = {
          path,
          label: path.split('.').slice(-2).join('.'),
          nodeType,
          reviewStatus,
          isExternal,
          x,
          y,
          width: 220,
          height: 72,
          inDegree: inDegrees[path] || 0,
          outDegree: outDegrees[path] || 0,
        };

        nodePositions.push(nodeObj);
        nMap.set(path, nodeObj);
      });
    });

    const renderedEdges = session.edges.map((e) => {
      const src = nMap.get(e.source_path);
      const tgt = e.target_path ? nMap.get(e.target_path) : null;
      return {
        edge: e,
        src,
        tgt,
      };
    });

    return { nodes: nodePositions, edgesWithPos: renderedEdges };
  }, [session.chunks, session.edges]);

  // Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0 || e.button === 1) {
      setIsPanning(true);
      setStartPanPos({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPanOffset({
        x: e.clientX - startPanPos.x,
        y: e.clientY - startPanPos.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  if (nodes.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-950 p-8">
        <div className="max-w-md text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-950 text-blue-400 border border-blue-800/80">
            <Info className="h-6 w-6" />
          </div>
          <h4 className="text-sm font-bold text-slate-200">
            Chưa Có Chunk Hay Quan Hệ Nào
          </h4>
          <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
            Phiên làm việc này hiện chưa có mục nội dung nào được bóc tách vào Staging.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden bg-slate-950 cursor-grab active:cursor-grabbing select-none touch-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Background Grid */}
      <svg className="absolute inset-0 pointer-events-none h-full w-full opacity-15">
        <defs>
          <pattern
            id="graphGrid"
            width={30 * zoomLevel}
            height={30 * zoomLevel}
            patternUnits="userSpaceOnUse"
            patternTransform={`translate(${panOffset.x}, ${panOffset.y})`}
          >
            <circle cx="2" cy="2" r="1.5" fill="#64748b" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#graphGrid)" />
      </svg>

      {/* Floating Canvas Controls */}
      <div className="absolute right-5 top-5 z-20 flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/90 p-1.5 shadow-xl backdrop-blur-md">
        <button
          type="button"
          onClick={() => setZoomLevel((z) => Math.min(2, z + 0.15))}
          className="rounded p-1.5 text-slate-300 hover:bg-slate-800 hover:text-white transition"
          title="Phóng to"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <span className="px-1.5 font-mono text-[11px] font-semibold text-slate-400">
          {Math.round(zoomLevel * 100)}%
        </span>
        <button
          type="button"
          onClick={() => setZoomLevel((z) => Math.max(0.3, z - 0.15))}
          className="rounded p-1.5 text-slate-300 hover:bg-slate-800 hover:text-white transition"
          title="Thu nhỏ"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <div className="h-4 w-px bg-slate-800 mx-1" />
        <button
          type="button"
          onClick={() => {
            setZoomLevel(1);
            setPanOffset({ x: 40, y: 40 });
          }}
          className="rounded p-1.5 text-slate-300 hover:bg-slate-800 hover:text-white transition"
          title="Đặt lại góc nhìn"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* Floating Relation Legend */}
      <div className="absolute left-5 top-5 z-20 hidden lg:flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/90 px-3 py-1.5 shadow-xl backdrop-blur-md text-[10px] font-mono">
        <span className="text-slate-400 font-bold uppercase text-[9px]">Quan Hệ:</span>
        <span className="flex items-center gap-1 text-sky-400"><span className="h-2 w-2 rounded-full bg-sky-400" />REF</span>
        <span className="flex items-center gap-1 text-emerald-400"><span className="h-2 w-2 rounded-full bg-emerald-400" />SUPPORT</span>
        <span className="flex items-center gap-1 text-rose-400"><span className="h-2 w-2 rounded-full bg-rose-400" />CONTRADICT</span>
        <span className="flex items-center gap-1 text-purple-400"><span className="h-2 w-2 rounded-full bg-purple-400" />DEFINE</span>
        <span className="flex items-center gap-1 text-indigo-400"><span className="h-2 w-2 rounded-full bg-indigo-400" />EXTEND</span>
        <span className="flex items-center gap-1 text-cyan-400"><span className="h-2 w-2 rounded-full bg-cyan-400" />DEPEND</span>
      </div>

      {/* Main SVG Graph Surface */}
      <svg
        className="absolute inset-0 h-full w-full pointer-events-auto"
        style={{
          transform: `translate3d(${panOffset.x}px, ${panOffset.y}px, 0) scale(${zoomLevel})`,
          transformOrigin: '0 0',
        }}
      >
        <defs>
          <marker
            id="arrow-REFERENCES"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
          </marker>
          <marker
            id="arrow-SUPPORTS"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981" />
          </marker>
          <marker
            id="arrow-CONTRADICTS"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#f43f5e" />
          </marker>
          <marker
            id="arrow-DEFINES"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#a855f7" />
          </marker>
          <marker
            id="arrow-EXTENDS"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#6366f1" />
          </marker>
          <marker
            id="arrow-EXEMPLIFIES"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b" />
          </marker>
          <marker
            id="arrow-DEPENDS_ON"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#06b6d4" />
          </marker>
          <marker
            id="arrow-SUPERSEDES"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444" />
          </marker>
          <marker
            id="arrow-SEE_ALSO"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
          </marker>
          <marker
            id="arrow-DEFAULT"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
          </marker>
        </defs>

        {/* 1. Render Directed Edges (Bezier Curves) */}
        {edgesWithPos.map(({ edge, src, tgt }, idx) => {
          if (!src) return null;
          const srcX = src.x + src.width / 2;
          const srcY = src.y + src.height / 2;

          let tgtX = srcX + 180;
          let tgtY = srcY + 90;

          if (tgt) {
            tgtX = tgt.x + tgt.width / 2;
            tgtY = tgt.y + tgt.height / 2;
          }

          const dx = tgtX - srcX;
          const cx1 = srcX + dx / 2;
          const cy1 = srcY;
          const cx2 = srcX + dx / 2;
          const cy2 = tgtY;

          const pathD = `M ${srcX} ${srcY} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${tgtX} ${tgtY}`;

          const isConnectedToHover =
            hoveredNode &&
            (edge.source_path === hoveredNode || edge.target_path === hoveredNode);
          const isSelected = selectedEdge === edge;

          let strokeColor = '#64748b';
          let markerId = 'arrow-DEFAULT';
          if (edge.relation_type === 'REFERENCES') {
            strokeColor = '#38bdf8';
            markerId = 'arrow-REFERENCES';
          } else if (edge.relation_type === 'SUPPORTS') {
            strokeColor = '#10b981';
            markerId = 'arrow-SUPPORTS';
          } else if (edge.relation_type === 'CONTRADICTS') {
            strokeColor = '#f43f5e';
            markerId = 'arrow-CONTRADICTS';
          } else if (edge.relation_type === 'DEFINES') {
            strokeColor = '#a855f7';
            markerId = 'arrow-DEFINES';
          } else if (edge.relation_type === 'EXTENDS') {
            strokeColor = '#6366f1';
            markerId = 'arrow-EXTENDS';
          } else if (edge.relation_type === 'EXEMPLIFIES') {
            strokeColor = '#f59e0b';
            markerId = 'arrow-EXEMPLIFIES';
          } else if (edge.relation_type === 'DEPENDS_ON') {
            strokeColor = '#06b6d4';
            markerId = 'arrow-DEPENDS_ON';
          } else if (edge.relation_type === 'SUPERSEDES') {
            strokeColor = '#ef4444';
            markerId = 'arrow-SUPERSEDES';
          } else if (edge.relation_type === 'SEE_ALSO') {
            strokeColor = '#64748b';
            markerId = 'arrow-SEE_ALSO';
          }

          return (
            <g
              key={idx}
              className="cursor-pointer group"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedEdge(edge);
              }}
            >
              {/* Invisible thicker hit-box */}
              <path
                d={pathD}
                fill="none"
                stroke="transparent"
                strokeWidth="20"
                className="pointer-events-stroke"
              />

              {/* Visual Stroke */}
              <path
                d={pathD}
                fill="none"
                stroke={strokeColor}
                strokeWidth={isSelected || isConnectedToHover ? '3.5' : '2'}
                strokeDasharray="none"
                markerEnd={`url(#${markerId})`}
                className="transition-all duration-150 group-hover:stroke-white opacity-85 group-hover:opacity-100"
              />

              {/* Edge Label Badge */}
              <foreignObject
                x={(srcX + tgtX) / 2 - 45}
                y={(srcY + tgtY) / 2 - 12}
                width="90"
                height="24"
                className="overflow-visible pointer-events-none"
              >
                <div
                  className="flex items-center justify-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-100 shadow border border-slate-800 bg-slate-950/90 truncate"
                  style={{ color: strokeColor }}
                >
                  {edge.relation_type.replace(/_/g, ' ').substring(0, 14)}
                </div>
              </foreignObject>
            </g>
          );
        })}

        {/* 2. Render Nodes */}
        {nodes.map((n) => {
          const isHovered = hoveredNode === n.path;
          const isConnected =
            hoveredNode &&
            session.edges.some(
              (e) =>
                (e.source_path === hoveredNode && e.target_path === n.path) ||
                (e.target_path === hoveredNode && e.source_path === n.path)
            );

          return (
            <foreignObject
              key={n.path}
              x={n.x}
              y={n.y}
              width={n.width}
              height={n.height}
              onMouseEnter={() => setHoveredNode(n.path)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={(e) => {
                e.stopPropagation();
                onSelectNode?.(n.path);
              }}
              className="overflow-visible cursor-pointer"
            >
              <div
                className={`flex h-full w-full flex-col justify-between rounded-xl p-2.5 shadow-lg backdrop-blur-md transition-all duration-150 ${
                  n.isExternal
                    ? 'border-2 border-dashed border-amber-600/80 bg-slate-950/95 shadow-amber-950/50'
                    : isHovered || isConnected
                    ? 'border border-brand-400 bg-brand-950/90 ring-2 ring-brand-400/40 shadow-brand-950'
                    : 'border border-slate-800 bg-slate-900/90 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 truncate">
                    {n.isExternal ? (
                      <span
                        className="rounded bg-amber-950 px-1 py-0.5 text-[8px] font-mono font-bold uppercase text-amber-300 border border-amber-700/80"
                        title="Chunk ngoại vi / chưa nạp nội bộ"
                      >
                        NGOẠI VI
                      </span>
                    ) : (
                      <span
                        className={`h-2 w-2 rounded-full shrink-0 ${
                          n.reviewStatus === 'REVIEWED' ? 'bg-emerald-400' : 'bg-amber-400'
                        }`}
                        title={n.reviewStatus === 'REVIEWED' ? 'Đã rà soát' : 'Chờ rà soát'}
                      />
                    )}
                    <span className="font-mono text-[11px] font-bold text-slate-100 truncate">
                      {n.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {n.nodeType && !n.isExternal && (
                      <span className="rounded bg-slate-800 px-1 py-0.2 text-[8px] font-mono uppercase text-slate-300 border border-slate-700">
                        {n.nodeType}
                      </span>
                    )}
                    {n.outDegree > 0 && (
                      <span className="rounded bg-blue-950 px-1 py-0.2 text-[9px] font-mono font-bold text-blue-300 border border-blue-800">
                        {n.outDegree} ra
                      </span>
                    )}
                    {n.inDegree > 0 && (
                      <span className="rounded bg-emerald-950 px-1 py-0.2 text-[9px] font-mono font-bold text-emerald-300 border border-emerald-800">
                        {n.inDegree} vào
                      </span>
                    )}
                  </div>
                </div>

                <div className={`font-mono text-[10px] truncate ${n.isExternal ? 'text-amber-400/90' : 'text-slate-400'}`}>
                  {n.path}
                </div>
              </div>
            </foreignObject>
          );
        })}
      </svg>

      {/* Edge Detail Drawer / Popover when selected */}
      {selectedEdge && (
        <div className="absolute bottom-5 left-5 z-30 max-w-md w-full rounded-xl border border-slate-700 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-md">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <span className="rounded-md border px-2 py-0.5 text-xs font-semibold bg-blue-950 text-blue-300 border-blue-800">
                {selectedEdge.relation_type}
              </span>
              <span className="text-xs font-bold text-slate-200">Chi Tiết Quan Hệ</span>
            </div>
            <button
              onClick={() => setSelectedEdge(null)}
              className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              <Minimize2 className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 space-y-2 text-xs">
            <div>
              <span className="text-[11px] text-slate-400">Nút nguồn (Source):</span>
              <div className="font-mono text-slate-100 bg-slate-950 p-1.5 rounded border border-slate-800 mt-0.5">
                {selectedEdge.source_path}
              </div>
            </div>

            <div>
              <span className="text-[11px] text-slate-400">Nút đích (Target):</span>
              <div className="font-mono text-slate-100 bg-slate-950 p-1.5 rounded border border-slate-800 mt-0.5">
                {selectedEdge.target_path}
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-start gap-2 pt-3 border-t border-slate-800">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => {
                  if (onSelectNode) onSelectNode(selectedEdge.source_path);
                }}
                className="rounded bg-slate-800 px-2.5 py-1 text-[11px] font-semibold text-brand-300 hover:bg-slate-700 transition"
              >
                Xem Nguồn →
              </button>
              {selectedEdge.target_path && (
                <button
                  type="button"
                  onClick={() => {
                    if (onSelectNode) onSelectNode(selectedEdge.target_path);
                  }}
                  className="rounded bg-slate-800 px-2.5 py-1 text-[11px] font-semibold text-blue-300 hover:bg-slate-700 transition"
                >
                  Xem Đích →
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
