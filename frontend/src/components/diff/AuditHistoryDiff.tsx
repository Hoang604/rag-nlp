import React, { useEffect, useState } from 'react';
import {
  Code,
  FileDiff,
  Filter,
  GitBranch,
  Layers,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { api } from '../../services/api';
import { SessionDiffResponse } from '../../types/diff';
import { StagingDocumentSession } from '../../types/staging';
import { WALRecord } from '../../types/api';
import { InlineDiffViewer } from './InlineDiffViewer';
import { MutationLogList } from './MutationLogList';
import { useToast } from '../toast/ToastContext';

interface AuditHistoryDiffProps {
  session: StagingDocumentSession;
  onRefreshSession?: () => Promise<void> | void;
}

export const AuditHistoryDiff: React.FC<AuditHistoryDiffProps> = ({
  session,
  onRefreshSession,
}) => {
  const { success, error } = useToast();
  const [diffData, setDiffData] = useState<SessionDiffResponse | null>(null);
  const [walRecords, setWalRecords] = useState<WALRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeStage, setActiveStage] = useState<number>(4);
  const [filterType, setFilterType] = useState<string>('ALL');
  const [activeTab, setActiveTab] = useState<'wal' | 'mutations'>('wal');
  const [replayingLsn, setReplayingLsn] = useState<number | null>(null);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [diffRes, walRes] = await Promise.all([
          api.getSessionDiff(session.doc_slug).catch(() => null),
          api.getWalJournal(session.doc_slug).catch(() => []),
        ]);
        setDiffData(diffRes);
        setWalRecords(walRes);
      } catch (err) {
        console.error('Failed to load audit diff or WAL data:', err);
      } finally {
        setLoading(false);
      }
    }
    void loadData();
  }, [session.doc_slug]);

  const stages = [
    {
      num: 1,
      name: 'Stage 1: AST Parser',
      desc: 'Cấu trúc AST nguyên bản ban đầu (Genesis)',
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
      desc: 'Khai thác quan hệ tham chiếu liên kết',
      icon: GitBranch,
    },
    {
      num: 4,
      name: 'Stage 4: Surgical Review',
      desc: 'Hiệu chỉnh phẫu thuật người & AI (Hiện tại)',
      icon: Sparkles,
    },
  ];

  // Stage-based filtering of diff entries and wal records
  const diffEntries = diffData?.diff_entries || [];

  const stageFilteredEntries = diffEntries.filter((entry) => {
    if (activeStage === 1) {
      // Stage 1: Genesis additions
      return entry.change_type === 'ADDED';
    }
    if (activeStage === 2) {
      // Stage 2: Context updates
      return entry.field_name === 'contextualized_text' || entry.description?.includes('ngữ cảnh');
    }
    if (activeStage === 3) {
      // Stage 3: Graph / edge relations
      return entry.field_name === 'edge' || entry.description?.includes('quan hệ') || entry.description?.includes('cạnh');
    }
    // Stage 4: All surgical changes
    return true;
  });

  const filteredEntries = stageFilteredEntries.filter((entry) => {
    if (filterType === 'ALL') return true;
    return entry.change_type === filterType;
  });

  const handleReplayLsn = async (targetLsn: number) => {
    setReplayingLsn(targetLsn);
    try {
      const res = await api.replaySession(session.doc_slug, targetLsn);
      success(
        'Replay hoàn tất',
        `Đã tái hiện thành công ${res.total_chunks} chunks và ${res.total_edges} edges tới LSN ${targetLsn}.`
      );
      if (onRefreshSession) {
        await onRefreshSession();
      }
    } catch (err) {
      error('Lỗi khi Replay', err instanceof Error ? err.message : String(err));
    } finally {
      setReplayingLsn(null);
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-slate-950 p-6 space-y-6">
      {/* Stage Progression Stepper with Functional Filtering */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 shadow">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Lộ Trình Xử Lý &amp; Kiểm Duyệt Pipeline (Lọc theo giai đoạn)
          </h4>
          <span className="text-[11px] text-brand-400 font-mono">
            Đang lọc: Giai đoạn {activeStage} ({stages.find((s) => s.num === activeStage)?.name})
          </span>
        </div>
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
                    ? 'border-brand-500 bg-brand-950/50 text-brand-300 ring-1 ring-brand-500/50'
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
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <FileDiff className="h-5 w-5 text-brand-400" />
              <h4 className="text-sm font-bold text-slate-100">
                So Sánh Biến Động (Diff vs Baseline AST)
              </h4>
              <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                {filteredEntries.length} thay đổi hiển thị
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
              Chưa có biến động nào được ghi nhận ở giai đoạn này.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEntries.map((entry, idx) => (
                <div key={idx} className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-bold text-slate-200">{entry.path}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        entry.change_type === 'ADDED'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : entry.change_type === 'DELETED'
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : 'bg-amber-950 text-amber-300 border border-amber-800'
                      }`}
                    >
                      {entry.change_type}
                    </span>
                  </div>
                  {entry.description && (
                    <p className="text-xs text-slate-400">{entry.description}</p>
                  )}
                  {entry.old_value !== undefined && entry.new_value !== undefined && (
                    <InlineDiffViewer
                      label={entry.field_name || 'Nội dung'}
                      oldText={
                        typeof entry.old_value === 'string'
                          ? entry.old_value
                          : JSON.stringify(entry.old_value, null, 2)
                      }
                      newText={
                        typeof entry.new_value === 'string'
                          ? entry.new_value
                          : JSON.stringify(entry.new_value, null, 2)
                      }
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 1 Col: WAL Journal & Audit History */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-1.5 rounded-lg bg-slate-900 p-1 border border-slate-800">
              <button
                type="button"
                onClick={() => setActiveTab('wal')}
                className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
                  activeTab === 'wal'
                    ? 'bg-brand-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                WAL Journal ({walRecords.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('mutations')}
                className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
                  activeTab === 'mutations'
                    ? 'bg-brand-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Mutations ({session.mutation_history.length})
              </button>
            </div>
          </div>

          {activeTab === 'wal' ? (
            <div className="space-y-3">
              {walRecords.length === 0 ? (
                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center text-xs text-slate-500">
                  Chưa có bản ghi WAL nào trong phiên làm việc này.
                </div>
              ) : (
                walRecords.map((rec) => (
                  <div
                    key={rec.lsn}
                    className="rounded-xl border border-slate-800 bg-slate-900/80 p-3.5 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono rounded bg-brand-950 px-2 py-0.5 text-[10px] font-bold text-brand-300 border border-brand-800">
                          LSN #{rec.lsn}
                        </span>
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300">
                          {rec.op_type}
                        </span>
                      </div>
                      <button
                        type="button"
                        disabled={replayingLsn !== null}
                        onClick={() => handleReplayLsn(rec.lsn)}
                        className="flex items-center gap-1 rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-300 hover:bg-brand-600 hover:text-white transition disabled:opacity-50"
                        title={`Tái hiện trạng thái phiên làm việc đến LSN ${rec.lsn}`}
                      >
                        <RotateCcw className={`h-3 w-3 ${replayingLsn === rec.lsn ? 'animate-spin' : ''}`} />
                        <span>Replay</span>
                      </button>
                    </div>

                    <p className="text-slate-200 leading-relaxed font-medium">
                      {rec.description}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/80">
                      <span>Tác tử: <span className="font-mono text-slate-400">{rec.actor}</span></span>
                      <span className="font-mono" title={rec.checksum}>
                        SHA: {rec.checksum.substring(0, 8)}...
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            <MutationLogList history={session.mutation_history} />
          )}
        </div>
      </div>
    </div>
  );
};

