import React from 'react';
import { Bot, Clock, User } from 'lucide-react';
import { StagingMutationRecord } from '../../types/staging';
import { formatISODateTime } from '../../utils/formatting';

interface MutationLogListProps {
  history: StagingMutationRecord[];
}

export const MutationLogList: React.FC<MutationLogListProps> = ({
  history,
}) => {
  if (!history || history.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-500">
        Chưa có nhật ký biến đổi nào được ghi nhận.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {history.map((rec, idx) => {
        const isAgent = rec.actor.toUpperCase().includes('AGENT');
        return (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs"
          >
            <div
              className={`mt-0.5 rounded-full p-1.5 ${
                isAgent
                  ? 'bg-blue-950 text-blue-400 border border-blue-800'
                  : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}
            >
              {isAgent ? <Bot className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
            </div>

            <div className="flex-1">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-200">{rec.actor}</span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                    {rec.action_type}
                  </span>
                </div>
                <span className="flex items-center gap-1 font-mono text-[11px] text-slate-500">
                  <Clock className="h-3 w-3" />
                  {formatISODateTime(rec.timestamp)}
                </span>
              </div>

              <p className="mt-1 text-slate-300">{rec.description}</p>

              {rec.diff_payload && (
                <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 font-mono text-[10px] text-slate-400 border border-slate-800">
                  {JSON.stringify(rec.diff_payload, null, 2)}
                </pre>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
