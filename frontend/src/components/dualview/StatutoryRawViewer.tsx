import React, { useEffect, useRef } from 'react';

export interface LineRange {
  start: number;
  end: number;
}

interface StatutoryRawViewerProps {
  rawText: string;
  searchTerm?: string;
  highlightRange?: LineRange | null;
  onLineClick?: (lineNumber: number, text: string) => void;
}

export const StatutoryRawViewer: React.FC<StatutoryRawViewerProps> = ({
  rawText,
  searchTerm = '',
  highlightRange = null,
  onLineClick,
}) => {
  const lineRefs = useRef<Map<number, HTMLTableRowElement>>(new Map());
  const lines = rawText.split('\n');

  // Auto-scroll to top of highlighted range when active chunk changes
  useEffect(() => {
    if (highlightRange?.start) {
      const el = lineRefs.current.get(highlightRange.start);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [highlightRange?.start, highlightRange?.end]);

  return (
    <div className="h-full overflow-y-auto bg-slate-950 p-4 font-mono text-xs text-slate-300 leading-relaxed border border-slate-800 rounded-lg">
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((rawLine, idx) => {
            const lineNum = idx + 1;
            const line = rawLine.replace(/\r$/, '');
            const isSearched =
              searchTerm && line.toLowerCase().includes(searchTerm.toLowerCase());
            const isInRange =
              highlightRange &&
              lineNum >= highlightRange.start &&
              lineNum <= highlightRange.end;
            const isRangeStart = highlightRange && lineNum === highlightRange.start;
            const isRangeEnd = highlightRange && lineNum === highlightRange.end;

            return (
              <tr
                key={idx}
                ref={(el) => {
                  if (el) lineRefs.current.set(lineNum, el);
                  else lineRefs.current.delete(lineNum);
                }}
                onClick={() => onLineClick?.(lineNum, line)}
                style={{ contentVisibility: 'auto', containIntrinsicSize: '24px' }}
                className={`cursor-pointer transition-all duration-150 ${
                  isInRange
                    ? `bg-brand-950/70 text-brand-100 ${
                        isRangeStart ? 'border-t-2 border-brand-500 ring-1 ring-brand-500/40' : ''
                      } ${isRangeEnd ? 'border-b-2 border-brand-500' : ''} shadow-inner`
                    : isSearched
                    ? 'bg-amber-950/40 text-amber-200 font-semibold'
                    : 'hover:bg-slate-900/60'
                }`}
              >
                <td className="w-12 select-none pr-3 text-right text-[11px] text-slate-600 align-top border-r border-slate-800/80">
                  {lineNum}
                </td>
                <td className="whitespace-pre-wrap break-words pl-3 py-0.5">
                  {line || ' '}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
