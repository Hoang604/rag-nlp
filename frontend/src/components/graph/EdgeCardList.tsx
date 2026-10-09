import React from 'react';
import { ArrowRight } from 'lucide-react';
import { GraphVisualizerEdge } from '../../types/api';
import { getRelationColor } from '../../utils/formatting';

interface EdgeCardListProps {
  edges: GraphVisualizerEdge[];
}

export const EdgeCardList: React.FC<EdgeCardListProps> = ({
  edges,
}) => {
  if (!edges || edges.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-8 text-center text-xs text-slate-400">
        Chưa có quan hệ (Graph Edge) nào được ghi nhận cho tài liệu này trong PostgreSQL.
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

              {/* Target Path */}
              <div className="rounded bg-slate-950 px-2.5 py-1 font-mono text-xs font-semibold text-slate-200 border border-slate-800">
                {edge.target_path}
              </div>
            </div>

            {edge.rationale && (
              <div className="w-full rounded-lg bg-slate-950/80 px-3 py-1.5 text-xs text-slate-300 border border-slate-800">
                <span className="font-semibold text-indigo-400">Luận cứ: </span>
                {edge.rationale}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
