import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Info,
  Maximize2,
  Minimize2,
  Trash2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { StagingDocumentSession, StagingEdge } from '../../types/staging';

interface GraphCanvasProps {
  session: StagingDocumentSession;
  onDeleteEdge: (edge: StagingEdge) => Promise<boolean>;
  onSelectNode?: (path: string) => void;
}

interface GraphNodePos {
  path: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  inDegree: number;
  outDegree: number;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  session,
  onDeleteEdge,
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

  // Extract all unique nodes involved in edges
  const { nodes, edgesWithPos } = useMemo(() => {
    const nodeSet = new Set<string>();
    const inDegrees: Record<string, number> = {};
    const outDegrees: Record<string, number> = {};

    for (const e of session.edges) {
      nodeSet.add(e.source_path);
      outDegrees[e.source_path] = (outDegrees[e.source_path] || 0) + 1;
      if (e.target_path) {
        nodeSet.add(e.target_path);
        inDegrees[e.target_path] = (inDegrees[e.target_path] || 0) + 1;
      }
    }

    // Cluster nodes by Article / Section prefix
    const sortedNodePaths = Array.from(nodeSet).sort();
    const nodePositions: GraphNodePos[] = [];
    const nMap = new Map<string, GraphNodePos>();

    const cols = Math.max(3, Math.ceil(Math.sqrt(sortedNodePaths.length * 1.5)));
    const colWidth = 260;
    const rowHeight = 110;

    sortedNodePaths.forEach((path, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);

      const x = col * colWidth + 50;
      const y = row * rowHeight + 50;

      const nodeObj: GraphNodePos = {
        path,
        label: path.split('.').slice(-2).join('.'),
        x,
        y,
        width: 210,
        height: 64,
        inDegree: inDegrees[path] || 0,
        outDegree: outDegrees[path] || 0,
      };

      nodePositions.push(nodeObj);
      nMap.set(path, nodeObj);
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
  }, [session.edges]);

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

  if (session.edges.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-950 p-8">
        <div className="max-w-md text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-950 text-blue-400 border border-blue-800/80">
            <Info className="h-6 w-6" />
          </div>
          <h4 className="text-sm font-bold text-slate-200">
            Chưa Có Cạnh Đồ Thị Quan Hệ Pháp Lý
          </h4>
          <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
            Văn bản này chưa có các liên kết dẫn chiếu, xử phạt, bãi bỏ hoặc quy chuẩn. Bạn có thể bấm nút &ldquo;Thêm Quan Hệ Mới&rdquo; để nối 2 điều khoản lại với nhau.
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
            id="arrow-MODIFIES_AND_REPLACES"
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
            id="arrow-SANCTIONS"
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
            id="arrow-OVERRIDES"
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
            id="arrow-EXEMPTS"
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
          if (edge.relation_type === 'MODIFIES_AND_REPLACES') {
            strokeColor = '#a855f7';
            markerId = 'arrow-MODIFIES_AND_REPLACES';
          } else if (edge.relation_type === 'SANCTIONS' || edge.relation_type === 'HAS_ADDITIONAL_SANCTION') {
            strokeColor = '#f59e0b';
            markerId = 'arrow-SANCTIONS';
          } else if (edge.relation_type.startsWith('REFERENCES')) {
            strokeColor = '#38bdf8';
            markerId = 'arrow-REFERENCES';
          } else if (edge.relation_type === 'OVERRIDES') {
            strokeColor = '#f43f5e';
            markerId = 'arrow-OVERRIDES';
          } else if (edge.relation_type === 'EXEMPTS') {
            strokeColor = '#10b981';
            markerId = 'arrow-EXEMPTS';
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
                strokeDasharray={edge.target_external_ref ? '4 3' : 'none'}
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
                className={`flex h-full w-full flex-col justify-between rounded-xl border p-2.5 shadow-lg backdrop-blur-md transition-all duration-150 ${
                  isHovered || isConnected
                    ? 'border-brand-400 bg-brand-950/90 ring-2 ring-brand-400/40 shadow-brand-950'
                    : 'border-slate-800 bg-slate-900/90 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between gap-1.5">
                  <span className="font-mono text-[11px] font-bold text-slate-100 truncate">
                    {n.label}
                  </span>
                  <div className="flex items-center gap-1">
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

                <div className="font-mono text-[10px] text-slate-400 truncate">
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
                {selectedEdge.target_path || selectedEdge.target_external_ref || 'Ngoại vi'}
              </div>
            </div>

            {selectedEdge.citation_text && (
              <div>
                <span className="text-[11px] text-slate-400">Căn cứ trích dẫn:</span>
                <div className="italic text-slate-300 bg-slate-950/80 p-2 rounded border border-slate-800 mt-0.5">
                  &ldquo;{selectedEdge.citation_text}&rdquo;
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={async () => {
                await onDeleteEdge(selectedEdge);
                setSelectedEdge(null);
              }}
              className="flex items-center gap-1.5 rounded-lg bg-rose-950 px-3 py-1.5 text-xs font-semibold text-rose-300 border border-rose-800 hover:bg-rose-900 transition"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Xóa Cạnh Này</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
