import React, { useMemo, useState } from 'react';
import {
  Filter,
  Grid,
  Layers,
  Plus,
  Search,
  Share2,
} from 'lucide-react';
import { CreateEdgePayload, DeleteEdgePayload } from '../../types/api';
import { StagingDocumentSession, StagingEdge } from '../../types/staging';
import { EdgeCardList } from './EdgeCardList';
import { EdgeEditorModal } from './EdgeEditorModal';
import { GraphCanvas } from './GraphCanvas';

interface VisualGraphInspectorProps {
  session: StagingDocumentSession;
  onAddEdge: (edge: CreateEdgePayload) => Promise<boolean>;
  onDeleteEdge: (payload: DeleteEdgePayload) => Promise<boolean>;
  onSelectNode?: (path: string) => void;
}

export const VisualGraphInspector: React.FC<VisualGraphInspectorProps> = ({
  session,
  onAddEdge,
  onDeleteEdge,
  onSelectNode,
}) => {
  const [viewMode, setViewMode] = useState<'canvas' | 'list'>('canvas');
  const [filterRelation, setFilterRelation] = useState<string>('');
  const [searchPath, setSearchPath] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const filteredEdges = useMemo(() => {
    return session.edges.filter((e) => {
      const matchRel =
        !filterRelation || e.relation_type.toUpperCase() === filterRelation.toUpperCase();
      const matchSearch =
        !searchPath ||
        e.source_path.toLowerCase().includes(searchPath.toLowerCase()) ||
        (e.target_path && e.target_path.toLowerCase().includes(searchPath.toLowerCase())) ||
        (e.citation_text && e.citation_text.toLowerCase().includes(searchPath.toLowerCase()));
      return matchRel && matchSearch;
    });
  }, [session.edges, filterRelation, searchPath]);

  const handleDelete = async (edge: StagingEdge) => {
    return await onDeleteEdge({
      source_path: edge.source_path,
      target_path: edge.target_path || null,
      relation_type: edge.relation_type,
    });
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950">
      {/* Top Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/90 px-6 py-3 shadow">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-950 text-blue-400 border border-blue-800/80">
            <Share2 className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-100">
                Đồ Thị Tri Thức Pháp Lý (Knowledge Graph)
              </h3>
              <span className="rounded-full bg-blue-950 px-2 py-0.5 font-mono text-[10px] font-bold text-blue-400 border border-blue-800">
                {session.edges.length} quan hệ
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Trực quan hóa mạng lưới liên kết xử phạt, dẫn chiếu, sửa đổi và ghi đè
            </p>
          </div>
        </div>

        {/* Center / Right Toolbar */}
        <div className="flex items-center gap-2.5">
          {/* View Mode Toggle */}
          <div className="flex items-center rounded-lg border border-slate-800 bg-slate-950 p-1">
            <button
              type="button"
              onClick={() => setViewMode('canvas')}
              className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition ${
                viewMode === 'canvas'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Canvas 2D</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition ${
                viewMode === 'list'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Grid className="h-3.5 w-3.5" />
              <span>Danh Sách Thẻ</span>
            </button>
          </div>

          {/* Add Edge Button */}
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow hover:bg-blue-500 transition"
          >
            <Plus className="h-4 w-4" />
            <span>Thêm Quan Hệ</span>
          </button>
        </div>
      </div>

      {/* Filter Bar (Active in List mode or Overlay) */}
      {viewMode === 'list' && (
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-900/60 px-6 py-2.5">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchPath}
              onChange={(e) => setSearchPath(e.target.value)}
              placeholder="Lọc theo source/target path hoặc trích dẫn..."
              className="w-full rounded-md border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-3 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              value={filterRelation}
              onChange={(e) => setFilterRelation(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 focus:border-blue-500 focus:outline-none"
            >
              <option value="">Tất cả loại quan hệ</option>
              <option value="MODIFIES_AND_REPLACES">Sửa đổi &amp; Thay thế</option>
              <option value="SANCTIONS">Xử phạt</option>
              <option value="HAS_ADDITIONAL_SANCTION">Phạt bổ sung</option>
              <option value="REFERENCES">Dẫn chiếu pháp luật</option>
              <option value="REFERENCES_TECHNICAL_STANDARD">Dẫn chiếu QCVN</option>
              <option value="OVERRIDES">Ghi đè ưu tiên</option>
              <option value="EXEMPTS">Miễn trừ</option>
              <option value="GUIDES">Hướng dẫn thi hành</option>
            </select>
          </div>
        </div>
      )}

      {/* Viewport Content */}
      <div className="flex-1 overflow-hidden relative">
        {viewMode === 'canvas' ? (
          <GraphCanvas
            session={{ ...session, edges: filteredEdges }}
            onDeleteEdge={handleDelete}
            onSelectNode={onSelectNode}
          />
        ) : (
          <div className="h-full overflow-y-auto p-6">
            <EdgeCardList edges={filteredEdges} onDeleteEdge={handleDelete} />
          </div>
        )}
      </div>

      {/* Add Edge Modal */}
      <EdgeEditorModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAddEdge={onAddEdge}
      />
    </div>
  );
};
