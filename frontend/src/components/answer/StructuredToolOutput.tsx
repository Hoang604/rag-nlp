import React, { useState } from 'react';
import {
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  FileText,
  GitBranch,
} from 'lucide-react';
import {
  isRecord,
  ParsedGraphLink,
  ParsedProvision,
  parseProvisionGroups,
  ToolTraceItem,
} from './toolTraceUtils';

function stripDuplicateDocTitle(context: string, docTitle: string): string {
  const trimmed = context.trim();
  if (!trimmed || !docTitle) return trimmed;
  if (trimmed.startsWith(docTitle)) {
    const rest = trimmed.slice(docTitle.length).replace(/^\s*>\s*/, '');
    return rest || trimmed;
  }
  return trimmed;
}

const ProvisionItemBlock: React.FC<{
  prov: ParsedProvision;
  docSlug: string;
  onOpenExplorer: (docSlug: string, path: string) => void;
}> = ({ prov, docSlug, onOpenExplorer }) => {
  const [showFullText, setShowFullText] = useState(false);
  const lines = prov.text.split('\n');
  const isLong = lines.length > 4 || prov.text.length > 260;
  const previewText =
    isLong && !showFullText
      ? `${lines.slice(0, 3).join('\n').slice(0, 260)}…`
      : prov.text;

  const foundInLabel = () => {
    if (!prov.found_in) return null;
    if (prov.found_in === 'both') {
      return (
        <span className="rounded bg-emerald-950/90 px-1.5 py-0.5 font-mono text-xs font-medium text-emerald-300">
          Cả hai nhánh
        </span>
      );
    }
    if (prov.found_in === 'semantic_only') {
      return (
        <span className="rounded bg-sky-950/90 px-1.5 py-0.5 font-mono text-xs font-medium text-sky-300">
          Ngữ nghĩa
        </span>
      );
    }
    return (
      <span className="rounded bg-amber-950/90 px-1.5 py-0.5 font-mono text-xs font-medium text-amber-300">
        Nguyên văn
      </span>
    );
  };

  return (
    <div className="py-2.5 first:pt-1 last:pb-0 space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {prov.rank !== undefined && (
            <span className="font-mono text-xs font-semibold text-brand-400 tabular-nums">
              #{prov.rank}
            </span>
          )}
          {foundInLabel()}
          <span className="truncate font-mono text-xs font-medium text-slate-200">
            {prov.path}
          </span>
          <span className="shrink-0 font-mono text-xs text-slate-400 tabular-nums">
            L{prov.start_line}–{prov.end_line}
          </span>
        </div>

        {docSlug && prov.path && (
          <button
            type="button"
            onClick={() => onOpenExplorer(docSlug, prov.path)}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors duration-150 focus:outline-none"
          >
            <span>Mở đồ thị</span>
            <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
          </button>
        )}
      </div>

      <pre className="whitespace-pre-wrap break-words rounded-xl bg-slate-950/80 px-3 py-2 font-mono text-xs leading-relaxed text-slate-200">
        {previewText}
      </pre>

      {isLong && (
        <button
          type="button"
          onClick={() => setShowFullText((v) => !v)}
          className="inline-flex items-center gap-1 text-xs font-medium text-brand-400 hover:text-brand-300 focus:outline-none"
        >
          {showFullText ? (
            <>
              <span>Thu gọn đoạn văn</span>
              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
            </>
          ) : (
            <>
              <span>Xem toàn văn ({lines.length} dòng)</span>
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            </>
          )}
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
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
        {result !== undefined
          ? JSON.stringify(result, null, 2)
          : '(Không có dữ liệu đầu ra)'}
      </pre>
    );
  }

  if (tool === 'hybrid_search' || tool === 'hierarchical_navigate') {
    const groups = parseProvisionGroups(result.groups);
    const docsMap = isRecord(result.documents) ? result.documents : {};
    const verbatimTotal =
      typeof result.verbatim_total === 'number' ? result.verbatim_total : null;
    const direction =
      typeof result.direction === 'string' ? result.direction : null;
    const anchorPath =
      typeof result.anchor_path === 'string' ? result.anchor_path : null;

    const totalProvs = groups.reduce((acc, g) => acc + g.provisions.length, 0);

    return (
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span>
            Tìm thấy <strong className="text-slate-200">{totalProvs}</strong>{' '}
            đoạn trong{' '}
            <strong className="text-slate-200">{groups.length}</strong> nhóm ngữ
            cảnh
          </span>
          {verbatimTotal !== null && (
            <span>· Khớp nguyên văn: {verbatimTotal}</span>
          )}
          {direction && anchorPath && (
            <span className="font-mono">
              · {direction} ({anchorPath})
            </span>
          )}
        </div>

        {groups.length === 0 ? (
          <div className="py-2 text-xs text-slate-400">
            Không có đoạn tài liệu nào khớp với truy vấn này.
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto overscroll-contain divide-y divide-slate-800/70 pe-1">
            {groups.map((grp, gIdx) => {
              const docEntry = docsMap[grp.doc_slug];
              const docTitle =
                isRecord(docEntry) && typeof docEntry.title === 'string'
                  ? docEntry.title
                  : grp.doc_slug;
              const shortContext = stripDuplicateDocTitle(
                grp.context || '',
                docTitle
              );

              return (
                <div
                  key={`${grp.doc_slug}-${gIdx}`}
                  className="py-3 first:pt-1 last:pb-0 space-y-2"
                >
                  <div className="space-y-0.5">
                    <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-slate-100">
                      <FileText
                        className="h-3.5 w-3.5 shrink-0 text-brand-500"
                        aria-hidden="true"
                      />
                      <span>{docTitle}</span>
                    </div>
                    {shortContext && (
                      <div className="ps-5 text-xs text-slate-400">
                        {shortContext}
                      </div>
                    )}
                  </div>

                  <div className="divide-y divide-slate-800/50 ps-5">
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
    const startLine =
      typeof result.start_line === 'number' ? result.start_line : 1;
    const endLine =
      typeof result.end_line === 'number' ? result.end_line : startLine;
    const totalLines =
      typeof result.total_lines === 'number' ? result.total_lines : endLine;
    const rawText = typeof result.raw_text === 'string' ? result.raw_text : '';
    const rawLines = rawText.split('\n');

    return (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-1.5 font-semibold text-slate-100">
            <FileText
              className="h-3.5 w-3.5 text-brand-500"
              aria-hidden="true"
            />
            <span>{title}</span>
          </div>
          <span className="font-mono text-xs text-slate-400 tabular-nums">
            Dòng L{startLine}–{endLine} / {totalLines}
          </span>
        </div>
        <div className="max-h-80 overflow-auto overscroll-contain rounded-xl bg-slate-950 p-2.5 font-mono text-xs leading-relaxed">
          {rawLines.map((ln, idx) => {
            const lineNum = startLine + idx;
            return (
              <div
                key={lineNum}
                className="flex rounded px-1 hover:bg-slate-900/60"
              >
                <span className="w-12 shrink-0 select-none pe-3 text-end text-slate-400 tabular-nums">
                  {lineNum}
                </span>
                <span className="flex-1 whitespace-pre-wrap break-words text-slate-200">
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
    const sourcePath =
      typeof result.source_path === 'string' ? result.source_path : '';
    const rawLinks = Array.isArray(result.links) ? result.links : [];
    const links: ParsedGraphLink[] = [];
    for (const l of rawLinks) {
      if (!isRecord(l)) continue;
      links.push({
        from_path: typeof l.from_path === 'string' ? l.from_path : sourcePath,
        direction: typeof l.direction === 'string' ? l.direction : 'OUTGOING',
        relation_type:
          typeof l.relation_type === 'string' ? l.relation_type : '',
        citation_text:
          typeof l.citation_text === 'string' ? l.citation_text : '',
        depth: typeof l.depth === 'number' ? l.depth : 1,
        total: typeof l.total === 'number' ? l.total : 0,
        groups: parseProvisionGroups(l.groups),
      });
    }

    return (
      <div className="space-y-2.5">
        <div className="text-xs text-slate-400">
          Nút xuất phát:{' '}
          <code className="font-mono text-brand-400">{sourcePath}</code> (
          {links.length} liên kết)
        </div>
        {links.length === 0 ? (
          <div className="py-2 text-xs text-slate-400">
            Không tìm thấy cạnh liên kết đồ thị nào từ nút này.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto overscroll-contain divide-y divide-slate-800/70 pe-1">
            {links.map((lnk, idx) => (
              <div
                key={`${lnk.from_path}-${lnk.relation_type}-${idx}`}
                className="py-3 first:pt-1 last:pb-0 space-y-2"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <GitBranch
                    className="h-3.5 w-3.5 text-brand-500"
                    aria-hidden="true"
                  />
                  <code className="font-mono text-xs text-slate-200">
                    {lnk.from_path}
                  </code>
                  <span className="rounded bg-brand-950 px-1.5 py-0.5 font-mono text-xs font-medium text-brand-300">
                    {lnk.relation_type} · bậc {lnk.depth}
                  </span>
                </div>
                {lnk.citation_text && (
                  <div className="ps-5 font-mono text-xs italic text-slate-300">
                    “{lnk.citation_text}”
                  </div>
                )}
                {lnk.groups.map((grp, gIdx) => (
                  <div
                    key={`${grp.doc_slug}-${gIdx}`}
                    className="divide-y divide-slate-800/50 ps-5"
                  >
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
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`rounded-md px-2 py-0.5 font-semibold ${
              accepted
                ? 'bg-emerald-950 text-emerald-300'
                : 'bg-rose-950 text-rose-300'
            }`}
          >
            {accepted ? 'Đã xác thực' : 'Từ chối'}
          </span>
          {abstained && (
            <span className="rounded-md bg-amber-950 px-2 py-0.5 text-xs text-amber-300">
              Từ chối trả lời
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
              const cStart =
                typeof c.start_line === 'number' ? c.start_line : 1;
              const cEnd = typeof c.end_line === 'number' ? c.end_line : cStart;
              return (
                <span
                  key={`${cPath}-${cIdx}`}
                  className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2 py-1 font-mono text-xs text-slate-200"
                >
                  <strong className="text-brand-400">#{cIdx}</strong>
                  <span>{cPath}</span>
                  <span className="text-slate-400 tabular-nums">
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
    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
};
