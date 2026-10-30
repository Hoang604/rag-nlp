import React, { useState } from 'react';
import { ArrowUpRight, FileText, FolderTree, GitBranch } from 'lucide-react';
import {
  isRecord,
  ParsedGraphLink,
  ParsedProvision,
  parseProvisionGroups,
  ToolTraceItem,
} from './toolTraceUtils';

const ProvisionItemBlock: React.FC<{
  prov: ParsedProvision;
  docSlug: string;
  onOpenExplorer: (docSlug: string, path: string) => void;
}> = ({ prov, docSlug, onOpenExplorer }) => {
  const [showFullText, setShowFullText] = useState(false);
  const lines = prov.text.split('\n');
  const isLong = lines.length > 4 || prov.text.length > 260;
  const previewText =
    isLong && !showFullText ? `${lines.slice(0, 3).join('\n').slice(0, 260)}...` : prov.text;

  const foundInBadge = () => {
    if (!prov.found_in) return null;
    if (prov.found_in === 'both') {
      return (
        <span className="rounded bg-emerald-950/90 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-300 border border-emerald-800/80">
          BOTH
        </span>
      );
    }
    if (prov.found_in === 'semantic_only') {
      return (
        <span className="rounded bg-sky-950/90 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-sky-300 border border-sky-800/80">
          SEMANTIC
        </span>
      );
    }
    return (
      <span className="rounded bg-amber-950/90 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-300 border border-amber-800/80">
        VERBATIM
      </span>
    );
  };

  return (
    <div className="rounded-lg border border-slate-800/90 bg-slate-950/90 p-2.5 space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          {prov.rank !== undefined && (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] font-bold text-brand-300">
              #{prov.rank}
            </span>
          )}
          {foundInBadge()}
          <span
            className="truncate font-mono text-[11px] font-medium text-slate-200"
            title={prov.path}
          >
            {prov.path}
          </span>
          <span className="shrink-0 font-mono text-[10px] text-slate-400">
            L{prov.start_line}–{prov.end_line}
          </span>
        </div>

        {docSlug && prov.path && (
          <button
            type="button"
            onClick={() => onOpenExplorer(docSlug, prov.path)}
            className="inline-flex shrink-0 items-center gap-1 rounded border border-slate-700/80 bg-slate-900 px-2 py-0.5 text-[10px] font-medium text-slate-300 hover:border-brand-500 hover:text-brand-300 transition"
          >
            <span>Mở đồ thị</span>
            <ArrowUpRight className="h-2.5 w-2.5" />
          </button>
        )}
      </div>

      <pre className="whitespace-pre-wrap break-words rounded bg-slate-900/60 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-slate-300">
        {previewText}
      </pre>

      {isLong && (
        <button
          type="button"
          onClick={() => setShowFullText((v) => !v)}
          className="text-[11px] font-medium text-brand-400 hover:text-brand-300"
        >
          {showFullText ? 'Thu gọn đoạn văn ▴' : `Xem toàn văn (${lines.length} dòng) ▾`}
        </button>
      )}
    </div>
  );
};

export const StructuredToolOutput: React.FC<{
  item: ToolTraceItem;
  onOpenExplorer: (docSlug: string, path: string) => void;
}> = ({ item, onOpenExplorer }) => {
  const { tool, result } = item;

  if (!isRecord(result)) {
    return (
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950 p-2.5 font-mono text-[11px] leading-relaxed text-slate-200">
        {result !== undefined ? JSON.stringify(result, null, 2) : '(Không có dữ liệu đầu ra)'}
      </pre>
    );
  }

  if (tool === 'hybrid_search' || tool === 'hierarchical_navigate') {
    const groups = parseProvisionGroups(result.groups);
    const docsMap = isRecord(result.documents) ? result.documents : {};
    const confidence =
      typeof result.confidence === 'string' ? result.confidence.toUpperCase() : null;
    const verbatimTotal =
      typeof result.verbatim_total === 'number' ? result.verbatim_total : null;
    const direction = typeof result.direction === 'string' ? result.direction : null;
    const anchorPath = typeof result.anchor_path === 'string' ? result.anchor_path : null;

    const totalProvs = groups.reduce((acc, g) => acc + g.provisions.length, 0);

    return (
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
          <span className="rounded bg-slate-800/90 px-2 py-0.5 font-medium text-slate-200">
            {totalProvs} đoạn văn trong {groups.length} nhóm ngữ cảnh
          </span>
          {confidence && (
            <span
              className={`rounded px-2 py-0.5 font-mono text-[10px] font-semibold ${
                confidence === 'HIGH'
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-amber-950 text-amber-300 border border-amber-800'
              }`}
            >
              Confidence: {confidence}
            </span>
          )}
          {verbatimTotal !== null && (
            <span className="rounded bg-slate-800/70 px-2 py-0.5 font-mono text-[10px] text-slate-300">
              Verbatim khớp: {verbatimTotal}
            </span>
          )}
          {direction && anchorPath && (
            <span className="rounded bg-slate-800/70 px-2 py-0.5 font-mono text-[10px] text-slate-300">
              {direction} từ {anchorPath}
            </span>
          )}
        </div>

        {groups.length === 0 ? (
          <div className="rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400">
            Không có đoạn tài liệu nào khớp với truy vấn này.
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto space-y-2.5 pr-1">
            {groups.map((grp, gIdx) => {
              const docEntry = docsMap[grp.doc_slug];
              const docTitle =
                isRecord(docEntry) && typeof docEntry.title === 'string'
                  ? docEntry.title
                  : grp.doc_slug;

              return (
                <div
                  key={`${grp.doc_slug}-${gIdx}`}
                  className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 space-y-2"
                >
                  <div className="space-y-0.5 border-b border-slate-800/80 pb-2">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                      <FileText className="h-3.5 w-3.5 shrink-0 text-brand-400" />
                      <span>{docTitle}</span>
                      <code className="font-mono text-[11px] font-normal text-slate-400">
                        ({grp.doc_slug})
                      </code>
                    </div>
                    {grp.context && (
                      <div className="flex items-center gap-1 pl-5 text-[11px] text-slate-400">
                        <FolderTree className="h-3 w-3 shrink-0 text-slate-500" />
                        <span className="truncate" title={grp.context}>
                          {grp.context}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    {grp.provisions.map((prov, pIdx) => (
                      <ProvisionItemBlock
                        key={`${prov.path}-${pIdx}`}
                        prov={prov}
                        docSlug={grp.doc_slug}
                        onOpenExplorer={onOpenExplorer}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (tool === 'get_raw') {
    const docSlug = typeof result.doc_slug === 'string' ? result.doc_slug : '';
    const title = typeof result.title === 'string' ? result.title : docSlug;
    const startLine = typeof result.start_line === 'number' ? result.start_line : 1;
    const endLine = typeof result.end_line === 'number' ? result.end_line : startLine;
    const totalLines = typeof result.total_lines === 'number' ? result.total_lines : endLine;
    const rawText = typeof result.raw_text === 'string' ? result.raw_text : '';
    const rawLines = rawText.split('\n');

    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-900/80 px-3 py-2 text-xs">
          <div className="flex items-center gap-2 text-slate-200">
            <FileText className="h-3.5 w-3.5 text-brand-400" />
            <span className="font-semibold">{title}</span>
            <code className="font-mono text-[11px] text-slate-400">({docSlug})</code>
          </div>
          <span className="font-mono text-[11px] text-slate-400">
            Dòng L{startLine}–{endLine} / tổng {totalLines} dòng
          </span>
        </div>
        <div className="max-h-80 overflow-auto p-2 font-mono text-[11px] leading-relaxed">
          {rawLines.map((ln, idx) => {
            const lineNum = startLine + idx;
            return (
              <div key={lineNum} className="flex hover:bg-slate-900/60 px-1 rounded">
                <span className="w-12 shrink-0 select-none pr-3 text-right text-slate-500">
                  {lineNum}
                </span>
                <span className="whitespace-pre-wrap break-words text-slate-200 flex-1">
                  {ln || ' '}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (tool === 'graph_traverse') {
    const sourcePath = typeof result.source_path === 'string' ? result.source_path : '';
    const rawLinks = Array.isArray(result.links) ? result.links : [];
    const links: ParsedGraphLink[] = [];
    for (const l of rawLinks) {
      if (!isRecord(l)) continue;
      links.push({
        from_path: typeof l.from_path === 'string' ? l.from_path : sourcePath,
        direction: typeof l.direction === 'string' ? l.direction : 'OUTGOING',
        relation_type: typeof l.relation_type === 'string' ? l.relation_type : '',
        citation_text: typeof l.citation_text === 'string' ? l.citation_text : '',
        depth: typeof l.depth === 'number' ? l.depth : 1,
        total: typeof l.total === 'number' ? l.total : 0,
        groups: parseProvisionGroups(l.groups),
      });
    }

    return (
      <div className="space-y-2.5">
        <div className="text-[11px] text-slate-300">
          Nút xuất phát: <code className="font-mono text-brand-300">{sourcePath}</code> (
          {links.length} liên kết)
        </div>
        {links.length === 0 ? (
          <div className="rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400">
            Không tìm thấy cạnh liên kết đồ thị nào từ nút này.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
            {links.map((lnk, idx) => (
              <div
                key={`${lnk.from_path}-${lnk.relation_type}-${idx}`}
                className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 space-y-2"
              >
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <GitBranch className="h-3.5 w-3.5 text-brand-400" />
                  <code className="font-mono text-[11px] text-slate-200">{lnk.from_path}</code>
                  <span className="rounded bg-brand-950 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-brand-300 border border-brand-800">
                    {lnk.relation_type} · depth {lnk.depth}
                  </span>
                </div>
                {lnk.citation_text && (
                  <div className="rounded border-l-2 border-brand-500 bg-slate-950/80 px-2.5 py-1.5 font-mono text-[11px] text-slate-300">
                    "{lnk.citation_text}"
                  </div>
                )}
                {lnk.groups.map((grp, gIdx) => (
                  <div key={`${grp.doc_slug}-${gIdx}`} className="space-y-1.5 pl-2">
                    {grp.provisions.map((prov, pIdx) => (
                      <ProvisionItemBlock
                        key={`${prov.path}-${pIdx}`}
                        prov={prov}
                        docSlug={grp.doc_slug}
                        onOpenExplorer={onOpenExplorer}
                      />
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (tool === 'submit_grounded_answer') {
    const accepted = Boolean(result.accepted);
    const abstained = Boolean(result.abstained);
    const message = typeof result.message === 'string' ? result.message : '';
    const citations = Array.isArray(result.citations) ? result.citations : [];

    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`rounded px-2 py-0.5 font-semibold ${
              accepted
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                : 'bg-rose-950 text-rose-300 border border-rose-800'
            }`}
          >
            {accepted ? 'Đã xác thực (Accepted)' : 'Từ chối'}
          </span>
          {abstained && (
            <span className="rounded bg-amber-950 px-2 py-0.5 text-[11px] text-amber-300 border border-amber-800">
              Abstained
            </span>
          )}
          <span className="text-slate-300">{message}</span>
        </div>

        {citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {citations.map((c, idx) => {
              if (!isRecord(c)) return null;
              const cIdx = typeof c.index === 'number' ? c.index : idx + 1;
              const cPath = typeof c.path === 'string' ? c.path : '';
              const cStart = typeof c.start_line === 'number' ? c.start_line : 1;
              const cEnd = typeof c.end_line === 'number' ? c.end_line : cStart;
              return (
                <span
                  key={`${cPath}-${cIdx}`}
                  className="inline-flex items-center gap-1 rounded border border-slate-800 bg-slate-900 px-2 py-1 font-mono text-[11px] text-slate-200"
                >
                  <strong className="text-brand-300">#{cIdx}</strong>
                  <span>{cPath}</span>
                  <span className="text-slate-400">
                    (L{cStart}–{cEnd})
                  </span>
                </span>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-950 p-2.5 font-mono text-[11px] leading-relaxed text-slate-200">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
};
