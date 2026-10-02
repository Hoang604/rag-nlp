import React, { useEffect, useState } from 'react';
import {
  Clock,
  Code,
  FileDiff,
  Filter,
  GitBranch,
  Layers,
  Sparkles,
} from 'lucide-react';
import { api } from '../../services/api';
import { SessionDiffResponse } from '../../types/diff';
import { StagingDocumentSession } from '../../types/staging';
import { InlineDiffViewer } from './InlineDiffViewer';
import { MutationLogList } from './MutationLogList';

interface AuditHistoryDiffProps {
  session: StagingDocumentSession;
}

export const AuditHistoryDiff: React.FC<AuditHistoryDiffProps> = ({ session }) => {
  const [diffData, setDiffData] = useState<SessionDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeStage, setActiveStage] = useState<number>(4);
  const [filterType, setFilterType] = useState<string>('ALL');

  useEffect(() => {
    async function loadDiff() {
      setLoading(true);
      try {
        const res = await api.getSessionDiff(session.doc_slug);
        setDiffData(res);
      } catch (err) {
        console.error('Failed to load session diff:', err);
      } finally {
        setLoading(false);
      }
    }
    void loadDiff();
  }, [session.doc_slug]);

  const stages = [
    {
      num: 1,
      name: 'Stage 1: AST Parser',
      desc: 'Cấu trúc AST nguyên bản ban đầu',
      icon: Layers,
    },
    {
      num: 2,
      name: 'Stage 2: Context Synthesis',
      desc: 'Tổng hợp tiền tố ngữ cảnh phả hệ',
      icon: Code,
    },
    {
      num: 3,
      name: 'Stage 3: Knowledge Graph',
      desc: 'Khai thác quan hệ tham chiếu',
      icon: GitBranch,
    },
    {
      num: 4,
      name: 'Stage 4: Surgical Review',
      desc: 'Hiệu chỉnh phẫu thuật người & AI',
      icon: Sparkles,
    },
  ];

  const diffEntries = diffData?.diff_entries || [];
  const filteredEntries = diffEntries.filter((entry) => {
    if (filterType === 'ALL') return true;
    return entry.change_type === filterType;
  });

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-slate-950 p-6 space-y-6">
      {/* Stage Progression Stepper */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">
          Lộ Trình Xử Lý &amp; Kiểm Duyệt Pipeline
        </h4>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          {stages.map((stage) => {
            const Icon = stage.icon;
            const isSelected = activeStage === stage.num;
            return (
              <button
                key={stage.num}
                type="button"
                onClick={() => setActiveStage(stage.num)}
                className={`flex items-start gap-3 rounded-lg border p-3 text-left transition ${
                  isSelected
                    ? 'border-brand-500 bg-brand-950/40 text-brand-300'
                    : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <div
                  className={`rounded-md p-2 ${
                    isSelected ? 'bg-brand-900/60 text-brand-400' : 'bg-slate-900 text-slate-500'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-200">{stage.name}</div>
                  <p className="text-[11px] text-slate-400 mt-0.5">{stage.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Diff Content Split */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Inline Diff Viewer */}
        <div className="space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <FileDiff className="h-5 w-5 text-brand-400" />
              <h4 className="text-sm font-bold text-slate-100">
                So Sánh Biến Động (Diff vs Baseline AST)
              </h4>
              <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                {diffData?.total_changes || 0} thay đổi
              </span>
            </div>

            {/* Filter Buttons */}
            <div className="flex items-center gap-1.5 text-xs">
              <Filter className="h-3.5 w-3.5 text-slate-500 mr-1" />
              {['ALL', 'MODIFIED', 'ADDED', 'DELETED'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setFilterType(t)}
                  className={`rounded px-2 py-1 text-[10px] font-semibold transition ${
                    filterType === t
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-xs text-slate-400">
              Đang tính toán diff với bản AST ban đầu...
            </div>
          ) : filteredEntries.length === 0 ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-xs text-slate-400">
              Chưa có biến động nào được ghi nhận so với AST gốc.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEntries.map((entry, idx) => (
                <div key={idx} className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-bold text-slate-200">{entry.path}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      entry.change_type === 'ADDED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' :
                      entry.change_type === 'DELETED' ? 'bg-rose-950 text-rose-300 border border-rose-800' :
                      'bg-amber-950 text-amber-300 border border-amber-800'
                    }`}>
                      {entry.change_type}
                    </span>
                  </div>
                  {entry.description && (
                    <p className="text-xs text-slate-400">{entry.description}</p>
                  )}
                  {entry.old_value !== undefined && entry.new_value !== undefined && (
                    <InlineDiffViewer
                      label={entry.field_name || 'Nội dung'}
                      oldText={typeof entry.old_value === 'string' ? entry.old_value : JSON.stringify(entry.old_value, null, 2)}
                      newText={typeof entry.new_value === 'string' ? entry.new_value : JSON.stringify(entry.new_value, null, 2)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 1 Col: Audit WAL Mutation Journal */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Clock className="h-5 w-5 text-brand-400" />
            <h4 className="text-sm font-bold text-slate-100">
              Nhật Ký Biến Động (Audit Trail)
            </h4>
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">
              {session.mutation_history.length} sự kiện
            </span>
          </div>

          <MutationLogList history={session.mutation_history} />
        </div>
      </div>
    </div>
  );
};
