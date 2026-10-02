import React from 'react';
import { computeTokenDiff } from '../../utils/diff';

interface InlineDiffViewerProps {
  oldText: string;
  newText: string;
  label?: string;
}

export const InlineDiffViewer: React.FC<InlineDiffViewerProps> = ({
  oldText,
  newText,
  label,
}) => {
  const diffs = computeTokenDiff(oldText || '', newText || '');

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed">
      {label && (
        <div className="mb-2 text-[11px] font-sans font-semibold text-slate-400">
          {label}
        </div>
      )}
      <div className="flex flex-wrap gap-x-0.5 whitespace-pre-wrap">
        {diffs.map((t, idx) => {
          if (t.type === 'added') {
            return (
              <span
                key={idx}
                className="bg-emerald-950/80 text-emerald-300 px-0.5 rounded border border-emerald-700/60 font-medium"
              >
                {t.value}
              </span>
            );
          }
          if (t.type === 'removed') {
            return (
              <span
                key={idx}
                className="bg-rose-950/80 text-rose-300 px-0.5 rounded border border-rose-700/60 line-through opacity-80"
              >
                {t.value}
              </span>
            );
          }
          return (
            <span key={idx} className="text-slate-300">
              {t.value}
            </span>
          );
        })}
      </div>
    </div>
  );
};
