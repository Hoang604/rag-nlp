import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  Globe,
  Link2,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { StagingDocumentSession, StagingEdge } from '../../types/staging';
import { CorpusDocument, CreateEdgePayload, SearchHit } from '../../types/api';
import { api } from '../../services/api';

interface UnresolvedBacklogModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: StagingDocumentSession | null;
  onAddEdge: (edge: CreateEdgePayload) => Promise<boolean>;
  onDeleteEdge: (edge: StagingEdge) => Promise<boolean>;
  onSelectChunk?: (path: string) => void;
}

export const UnresolvedBacklogModal: React.FC<UnresolvedBacklogModalProps> = ({
  isOpen,
  onClose,
  session,
  onAddEdge,
  onDeleteEdge,
  onSelectChunk,
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState<StagingEdge | null>(null);
  const [targetSearch, setTargetSearch] = useState('');
  const [selectedCandidatePath, setSelectedCandidatePath] = useState('');
  const [customTargetPath, setCustomTargetPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [, setServerCount] = useState(0);

  // Cross-Document Scope State
  const [corpusDocs, setCorpusDocs] = useState<CorpusDocument[]>([]);
  const [selectedScope, setSelectedScope] = useState<string>('CURRENT');
  const [externalHits, setExternalHits] = useState<SearchHit[]>([]);
  const [searchingExternal, setSearchingExternal] = useState(false);

  useEffect(() => {
    if (!isOpen || !session?.doc_slug) return;
    let isMounted = true;
    setLoading(true);

    // Fetch backlog count
    api
      .getUnresolvedBacklog(session.doc_slug)
      .then((res) => {
        if (isMounted && res.items) {
          setServerCount(res.total_unresolved ?? res.items.length);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    // Fetch all corpus documents for cross-document resolution
    api
      .documents()
      .then((docs) => {
        if (isMounted) {
          setCorpusDocs(docs);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [isOpen, session?.doc_slug]);

  // Search in external document when scope is another corpus doc
  useEffect(() => {
    if (selectedScope === 'CURRENT' || selectedScope === 'CUSTOM') {
      setExternalHits([]);
      setSearchingExternal(false);
      return;
    }

    const timer = setTimeout(async () => {
      setSearchingExternal(true);
      try {
        const queryText = targetSearch.trim() || 'a';
        const resp = await api.search({
          query: queryText,
          limit: 15,
          doc_slugs: [selectedScope],
        });
        setExternalHits(resp.hits || []);
      } catch {
        setExternalHits([]);
      } finally {
        setSearchingExternal(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [selectedScope, targetSearch]);

  if (!isOpen || !session) return null;

  // Unresolved edges: target_path does not start with doc_slug or does not exist in session chunks
  const localUnresolvedEdges = session.edges.filter((e) => {
    if (!e.target_path) return true;
    const isInternal = session.chunks.some((c) => c.path === e.target_path);
    return !isInternal;
  });

  const filteredEdges = localUnresolvedEdges.filter(
    (e) =>
      e.source_path.toLowerCase().includes(filterQuery.toLowerCase()) ||
      e.target_path.toLowerCase().includes(filterQuery.toLowerCase()) ||
      e.relation_type.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const candidateChunks = session.chunks.filter((c) => {
    if (!targetSearch) return true;
    const q = targetSearch.toLowerCase();
    return (
      c.path.toLowerCase().includes(q) ||
      c.verbatim_text.toLowerCase().includes(q)
    );
  });

  const handleResolveToChunk = async () => {
    const finalTargetPath =
      selectedScope === 'CUSTOM'
        ? customTargetPath.trim()
        : selectedCandidatePath.trim();

    if (!selectedItem || !finalTargetPath) return;
    try {
      // 1. Delete old unresolved edge
      await onDeleteEdge(selectedItem);
      // 2. Add new edge pointing to target chunk
      await onAddEdge({
        source_path: selectedItem.source_path,
        target_path: finalTargetPath,
        relation_type: selectedItem.relation_type,
      });
      setSelectedItem(null);
      setSelectedCandidatePath('');
      setCustomTargetPath('');
    } catch {
      // Handled by toast
    }
  };

  const isResolveDisabled =
    selectedScope === 'CUSTOM'
      ? !customTargetPath.trim()
      : !selectedCandidatePath.trim();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex h-[85vh] w-full max-w-4xl flex-col rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-950/80 text-amber-400 border border-amber-700/60">
              <ExternalLink className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-100">
                  Quản Lý Tham Chiếu Chưa Phân Giải (Reference Backlog)
                </h3>
                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-mono font-semibold text-amber-400 border border-amber-500/30">
                  {localUnresolvedEdges.length} mục
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Các liên kết ngoài hoặc neo văn bản trỏ tới tài liệu khác trong corpus hoặc chưa nạp vào hệ thống.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search / Filter Bar */}
        <div className="border-b border-slate-800 bg-slate-950/40 px-6 py-3 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Lọc theo nguồn, đích, hoặc loại quan hệ..."
              className="w-full rounded-lg border border-slate-700 bg-slate-950 py-1.5 pl-9 pr-3 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
            />
          </div>
          {loading && (
            <span className="text-xs text-slate-400 animate-pulse">
              Đang tải từ server...
            </span>
          )}
        </div>

        {/* Modal Content: Split Pane */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Unresolved Reference List */}
          <div className="w-1/2 border-r border-slate-800 overflow-y-auto p-4 space-y-2.5">
            {filteredEdges.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center p-6 text-slate-400">
                <CheckCircle className="h-10 w-10 text-emerald-400 mb-2 opacity-80" />
                <p className="text-sm font-semibold text-slate-200">
                  Không Có Tham Chiếu Chưa Giải Quyết
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Toàn bộ các cạnh quan hệ trong tài liệu đều đã gắn kết 1:1 nội bộ.
                </p>
              </div>
            ) : (
              filteredEdges.map((edge, idx) => {
                const isSelected = selectedItem === edge;
                return (
                  <div
                    key={idx}
                    onClick={() => {
                      setSelectedItem(edge);
                      setSelectedCandidatePath('');
                      setCustomTargetPath(edge.target_path || '');
                      setTargetSearch('');
                    }}
                    className={`p-3 rounded-xl border cursor-pointer transition ${
                      isSelected
                        ? 'border-brand-500 bg-brand-950/40 ring-1 ring-brand-500/40 shadow'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="rounded bg-amber-950 px-1.5 py-0.5 text-[9px] font-mono font-bold text-amber-300 border border-amber-800/80">
                        {edge.relation_type}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteEdge(edge);
                        }}
                        title="Bỏ qua và xóa cạnh chưa giải quyết này"
                        className="rounded p-1 text-slate-400 hover:bg-rose-950 hover:text-rose-400 transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <div className="text-xs space-y-1">
                      <div className="flex items-center gap-1.5 text-slate-300 truncate">
                        <span className="text-[10px] text-slate-400 shrink-0">Nguồn:</span>
                        <span className="font-mono text-[11px] text-slate-200 truncate">
                          {edge.source_path}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-amber-300 truncate">
                        <span className="text-[10px] text-slate-400 shrink-0">Đích ngoại:</span>
                        <span className="font-mono text-[11px] font-semibold truncate">
                          {edge.target_path}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Right: Resolution Pane */}
          <div className="w-1/2 flex flex-col p-5 bg-slate-950/20 overflow-y-auto">
            {selectedItem ? (
              <div className="space-y-4">
                <div className="pb-3 border-b border-slate-800">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Phân Giải Liên Kết Tham Chiếu
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Gắn liên kết từ chunk nguồn sang một chunk hợp lệ trong tài liệu hiện tại hoặc tài liệu khác trong corpus.
                  </p>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="rounded-lg bg-slate-950 p-2.5 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block mb-0.5">Chunk nguồn:</span>
                    <span className="font-mono font-semibold text-brand-300">
                      {selectedItem.source_path}
                    </span>
                  </div>

                  <div className="rounded-lg bg-amber-950/30 p-2.5 border border-amber-800/40">
                    <span className="text-[10px] text-amber-400 block mb-0.5">
                      Đích tham chiếu chưa tìm thấy:
                    </span>
                    <span className="font-mono font-semibold text-amber-200">
                      {selectedItem.target_path}
                    </span>
                  </div>
                </div>

                {/* Scope Selector */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <Globe className="h-3.5 w-3.5 text-brand-400" />
                    <span>Phạm Vi Tài Liệu Đích:</span>
                  </label>
                  <select
                    value={selectedScope}
                    onChange={(e) => {
                      setSelectedScope(e.target.value);
                      setSelectedCandidatePath('');
                    }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 focus:border-brand-500 focus:outline-none"
                  >
                    <option value="CURRENT">
                      Tài liệu hiện tại ({session.title || session.doc_slug})
                    </option>
                    {corpusDocs
                      .filter((d) => d.doc_slug !== session.doc_slug)
                      .map((d) => (
                        <option key={d.doc_slug} value={d.doc_slug}>
                          Corpus: {d.title} ({d.doc_slug} - {d.chunk_count} chunks)
                        </option>
                      ))}
                    <option value="CUSTOM">
                      Đường dẫn tùy chỉnh / Ngoại vi (Custom LTree Path)
                    </option>
                  </select>
                </div>

                {/* Candidate Search or Custom Path Input */}
                {selectedScope === 'CUSTOM' ? (
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-300">
                      Nhập Đường Dẫn LTree Đích:
                    </label>
                    <input
                      type="text"
                      value={customTargetPath}
                      onChange={(e) => setCustomTargetPath(e.target.value)}
                      placeholder="ví dụ: doc_quy_trinh.sec_2.p_3"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-mono text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-400">
                      Đường dẫn này sẽ được ghi nhận vào đồ thị quan hệ và cơ sở dữ liệu PostgreSQL.
                    </p>
                  </div>
                ) : selectedScope === 'CURRENT' ? (
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-300">
                      Chọn Chunk Đích Trong Tài Liệu Hiện Tại:
                    </label>
                    <input
                      type="text"
                      value={targetSearch}
                      onChange={(e) => setTargetSearch(e.target.value)}
                      placeholder="Tìm kiếm chunk đích theo tiêu đề hoặc nội dung..."
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
                    />

                    <div className="max-h-56 overflow-y-auto space-y-1.5 rounded-lg border border-slate-800 bg-slate-950 p-2">
                      {candidateChunks.slice(0, 15).map((c) => {
                        const isCandidateSelected = selectedCandidatePath === c.path;
                        return (
                          <div
                            key={c.path}
                            onClick={() => setSelectedCandidatePath(c.path)}
                            className={`p-2 rounded-lg cursor-pointer text-xs transition ${
                              isCandidateSelected
                                ? 'bg-brand-950 border border-brand-500 text-brand-200'
                                : 'hover:bg-slate-900 border border-transparent text-slate-300'
                            }`}
                          >
                            <div className="font-mono text-[10px] font-bold text-brand-400 truncate">
                              {c.path}
                            </div>
                            <div className="truncate text-[11px] text-slate-400 mt-0.5">
                              {c.verbatim_text.substring(0, 80)}
                            </div>
                            {onSelectChunk && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onSelectChunk(c.path);
                                }}
                                className="text-[9px] text-brand-400 hover:underline mt-0.5 inline-block"
                              >
                                Xem trong Studio →
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-300">
                        Chọn Chunk Đích Từ Tài Liệu [{selectedScope}]:
                      </label>
                      {searchingExternal && (
                        <span className="text-[10px] text-slate-400 animate-pulse">
                          Đang tìm kiếm...
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={targetSearch}
                      onChange={(e) => setTargetSearch(e.target.value)}
                      placeholder="Tìm kiếm nội dung chunk trong tài liệu đích..."
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
                    />

                    <div className="max-h-56 overflow-y-auto space-y-1.5 rounded-lg border border-slate-800 bg-slate-950 p-2">
                      {externalHits.length === 0 ? (
                        <div className="py-4 text-center text-xs text-slate-500">
                          {searchingExternal ? 'Đang truy hồi…' : 'Nhập từ khóa để tìm chunk trong tài liệu này'}
                        </div>
                      ) : (
                        externalHits.map((h) => {
                          const isCandidateSelected = selectedCandidatePath === h.path;
                          return (
                            <div
                              key={h.path}
                              onClick={() => setSelectedCandidatePath(h.path)}
                              className={`p-2 rounded-lg cursor-pointer text-xs transition ${
                                isCandidateSelected
                                  ? 'bg-brand-950 border border-brand-500 text-brand-200'
                                  : 'hover:bg-slate-900 border border-transparent text-slate-300'
                              }`}
                            >
                              <div className="font-mono text-[10px] font-bold text-brand-400 truncate">
                                {h.path}
                              </div>
                              <div className="truncate text-[11px] text-slate-400 mt-0.5">
                                {h.verbatim_text.substring(0, 80)}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}

                <div className="pt-2 flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => onDeleteEdge(selectedItem)}
                    className="flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-rose-300 hover:bg-rose-950 transition"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Bỏ qua cạnh</span>
                  </button>
                  <button
                    type="button"
                    disabled={isResolveDisabled}
                    onClick={handleResolveToChunk}
                    className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-brand-500 disabled:opacity-50 transition"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    <span>Gắn Kết Tham Chiếu</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 text-slate-400">
                <AlertTriangle className="h-8 w-8 text-slate-600 mb-2" />
                <p className="text-xs text-slate-400">
                  Chọn một tham chiếu từ danh sách bên trái để kiểm tra và tiến hành phân giải.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
