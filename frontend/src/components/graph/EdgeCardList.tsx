import React from 'react';
import { ArrowRight, Trash2 } from 'lucide-react';
import { StagingEdge } from '../../types/staging';
import { getRelationColor } from '../../utils/formatting';

interface EdgeCardListProps {
  edges: StagingEdge[];
  onDeleteEdge: (edge: StagingEdge) => void;
}

export const EdgeCardList: React.FC<EdgeCardListProps> = ({
  edges,
  onDeleteEdge,
}) => {
  if (!edges || edges.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-8 text-center text-xs text-slate-400">
        Chưa có quan hệ pháp lý (Graph Edge) nào được gắn vào văn bản này.
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      {edges.map((edge, idx) => {
        const color = getRelationColor(edge.relation_type);
        return (
          <div
            key={idx}
            className={`flex items-center justify-between gap-4 rounded-xl border p-4 transition ${color.bg} ${color.border}`}
          >
            <div className="flex flex-1 flex-wrap items-center gap-3">
              {/* Source Path */}
              <div className="rounded bg-slate-950 px-2.5 py-1 font-mono text-xs font-semibold text-slate-200 border border-slate-800">
                {edge.source_path}
              </div>

              {/* Relation Badge */}
              <div className="flex items-center gap-1.5">
                <ArrowRight className="h-4 w-4 text-slate-500" />
                <span
                  className={`rounded-md border px-2.5 py-0.5 text-xs font-semibold ${color.badge}`}
                >
                  {color.label}
                </span>
                <ArrowRight className="h-4 w-4 text-slate-500" />
              </div>

              {/* Target Path or External Ref */}
              <div className="rounded bg-slate-950 px-2.5 py-1 font-mono text-xs font-semibold text-slate-200 border border-slate-800">
                {edge.target_path || edge.target_external_ref || 'External Ref'}
              </div>

              {/* Citation Text */}
              {edge.citation_text && (
                <div className="text-xs italic text-slate-400">
                  &ldquo;{edge.citation_text}&rdquo;
                </div>
              )}
            </div>

            <button
              onClick={() => onDeleteEdge(edge)}
              title="Xóa cạnh quan hệ này"
              className="rounded p-1.5 text-slate-400 hover:bg-rose-950 hover:text-rose-400 transition"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
