import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, FileText, RefreshCw, Search, X } from 'lucide-react';
import { CorpusDocument, GraphVisualizerResponse } from '../../types/api';
import { DocumentTreeNode, DocumentTreeResponse } from '../../types/tree';
import { useI18n } from '../../i18n/I18nContext';
import { MindMapCanvas } from './MindMapCanvas';
import { NodeInspectorPanel } from '../studio/NodeInspectorPanel';

interface CorpusExplorerPanelProps {
  documents: CorpusDocument[];
  activeDocSlug: string;
  onSelectDoc: (slug: string) => void;
  treeData: DocumentTreeResponse | null;
  graphData: GraphVisualizerResponse | null;
  selectedPath: string;
  onSelectPath: (path: string) => void;
  onRefresh: () => void;
  onOpenGlobalGrep: () => void;
}

function humanizeSegment(seg: string): string {
  const lower = seg.toLowerCase();
  if (lower.startsWith('chuong_')) return `Chương ${seg.slice(7).replace(/_/g, ' ').toUpperCase()}`;
  if (lower.startsWith('phan_')) return `Phần ${seg.slice(5).replace(/_/g, ' ').toUpperCase()}`;
  if (lower.startsWith('muc_')) return `Mục ${seg.slice(4).replace(/_/g, ' ').toUpperCase()}`;
  if (lower.startsWith('tieu_muc_')) return `Tiểu mục ${seg.slice(9).replace(/_/g, ' ').toUpperCase()}`;
  if (lower.startsWith('dieu_')) return `Điều ${seg.slice(5).replace(/_/g, ' ')}`;
  if (lower.startsWith('khoan_')) return `Khoản ${seg.slice(6).replace(/_/g, ' ')}`;
  if (lower.startsWith('phu_luc_')) return `Phụ lục ${seg.slice(8).replace(/_/g, ' ').toUpperCase()}`;
  return seg;
}

function findFirstBreadcrumbList(node: DocumentTreeNode): string[] | null {
  if (node.contextualized_text) {
    const m = node.contextualized_text.match(/^\[([^\]]+)\]/);
    if (m && m[1].includes(' > ')) {
      return m[1].split(' > ').map((s) => s.trim());
    }
  }
  if (node.children) {
    for (const child of node.children) {
      const found = findFirstBreadcrumbList(child);
      if (found) return found;
    }
  }
  return null;
}

function normalizeTreeNode(
  node: DocumentTreeNode,
  rootPath: string,
  depth: number
): DocumentTreeNode {
  const validChildren = (node.children || [])
    .filter((child) => {
      // Drop bogus prefix-only empty nodes (e.g. path="baohiem" under root="baohiem.luat_...")
      if (
        depth === 0 &&
        !child.path.startsWith(`${rootPath}.`) &&
        (!child.children || child.children.length === 0) &&
        !child.verbatim_text
      ) {
        return false;
      }
      return true;
    })
    .map((child) => normalizeTreeNode(child, rootPath, depth + 1));

  const lastSeg = node.path.split('.').pop() || node.path;
  let resolvedLabel = node.label;
  if (depth > 0 && (!resolvedLabel || resolvedLabel === lastSeg)) {
    const crumbs = findFirstBreadcrumbList(node);
    if (crumbs && crumbs.length > depth) {
      resolvedLabel = crumbs[depth];
    } else {
      resolvedLabel = humanizeSegment(lastSeg);
    }
  }

  let startLine = node.start_line;
  let endLine = node.end_line;
  if (validChildren.length > 0 && !node.verbatim_text) {
    const starts = validChildren.map((c) => c.start_line).filter((n) => n > 0);
    const ends = validChildren.map((c) => c.end_line).filter((n) => n > 0);
    if (starts.length > 0 && ends.length > 0) {
      startLine = Math.min(...starts);
      endLine = Math.max(...ends);
    }
  }

  return {
    ...node,
    label: resolvedLabel,
    start_line: startLine,
    end_line: endLine,
    children: validChildren,
  };
}

export const CorpusExplorerPanel: React.FC<CorpusExplorerPanelProps> = ({
  documents,
  activeDocSlug,
  onSelectDoc,
  treeData,
  graphData,
  selectedPath,
  onSelectPath,
  onRefresh,
  onOpenGlobalGrep,
}) => {
  const { t } = useI18n();
  const [isInspectorOpen, setIsInspectorOpen] = useState<boolean>(true);
  const [isDocMenuOpen, setIsDocMenuOpen] = useState<boolean>(false);
  const [quickQuery, setQuickQuery] = useState<string>('');
  const docMenuRef = useRef<HTMLDivElement | null>(null);

  // Close custom document dropdown on outside click or Escape
  useEffect(() => {
    if (!isDocMenuOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (docMenuRef.current && !docMenuRef.current.contains(e.target as Node)) {
        setIsDocMenuOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsDocMenuOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isDocMenuOpen]);

function buildDefaultCollapsedSet(
  root: DocumentTreeNode | null | undefined,
  activePath?: string
): Set<string> {
  const set = new Set<string>();
  if (!root) return set;

  function walk(node: DocumentTreeNode, depth: number) {
    if (depth >= 1 && node.children && node.children.length > 0) {
      set.add(node.path);
    }
    if (node.children) {
      node.children.forEach((c) => walk(c, depth + 1));
    }
  }
  walk(root, 0);

  // Auto-open the first chapter by default so the mind map shows 3 levels immediately on open
  if (root.children && root.children.length > 0) {
    set.delete(root.children[0].path);
  }

  // Ensure activePath and all its ancestors are expanded
  if (activePath && activePath.startsWith(root.path)) {
    const parts = activePath.split('.');
    for (let i = 1; i <= parts.length; i++) {
      set.delete(parts.slice(0, i).join('.'));
    }
  }

  return set;
}

  const normalizedRoot = useMemo(() => {
    if (!treeData?.root) return null;
    return normalizeTreeNode(treeData.root, treeData.root.path, 0);
  }, [treeData]);

  // Synchronously initialize collapsedPaths so the first render never layouts an uncollapsed 150-node tree
  const [collapsedState, setCollapsedState] = useState<{
    docSlug: string;
    paths: Set<string>;
  }>(() => ({
    docSlug: treeData?.doc_slug || '',
    paths: buildDefaultCollapsedSet(normalizedRoot, selectedPath),
  }));

  const collapsedPaths = useMemo(() => {
    if (treeData?.doc_slug && collapsedState.docSlug !== treeData.doc_slug) {
      return buildDefaultCollapsedSet(normalizedRoot, selectedPath);
    }
    return collapsedState.paths;
  }, [treeData?.doc_slug, collapsedState, normalizedRoot, selectedPath]);

  // Sync state when document tree changes
  useEffect(() => {
    if (!normalizedRoot || !treeData) return;
    if (collapsedState.docSlug !== treeData.doc_slug) {
      setCollapsedState({
        docSlug: treeData.doc_slug,
        paths: buildDefaultCollapsedSet(normalizedRoot, selectedPath),
      });
      if (!selectedPath) {
        onSelectPath(normalizedRoot.path);
      }
    }
  }, [normalizedRoot, treeData, collapsedState.docSlug, selectedPath, onSelectPath]);

  const expandPathAndAncestors = (targetPath: string) => {
    if (!targetPath || !treeData?.doc_slug) return;
    setCollapsedState((prev) => {
      const base =
        prev.docSlug === treeData.doc_slug
          ? prev.paths
          : buildDefaultCollapsedSet(normalizedRoot, targetPath);
      const next = new Set(base);
      const parts = targetPath.split('.');
      for (let i = 1; i <= parts.length; i++) {
        next.delete(parts.slice(0, i).join('.'));
      }
      return { docSlug: treeData.doc_slug, paths: next };
    });
    setIsInspectorOpen(true);
  };

  // Expand selected node and its ancestor chain when selectedPath changes externally (e.g. from Q&A tab)
  useEffect(() => {
    if (!selectedPath || !treeData?.doc_slug) return;
    expandPathAndAncestors(selectedPath);
  }, [selectedPath, treeData?.doc_slug]);

  const handleSelectAndExpand = (path: string) => {
    expandPathAndAncestors(path);
    onSelectPath(path);
  };

  const handleToggleCollapse = (path: string) => {
    const slug = treeData?.doc_slug || '';
    setCollapsedState((prev) => {
      const next = new Set(prev.docSlug === slug ? prev.paths : collapsedPaths);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return { docSlug: slug, paths: next };
    });
  };

  // Expand one more level of currently visible collapsed frontier nodes
  const handleExpandOneLevel = () => {
    if (!normalizedRoot) return;
    const slug = treeData?.doc_slug || '';
    setCollapsedState((prev) => {
      const current = prev.docSlug === slug ? prev.paths : collapsedPaths;
      const next = new Set(current);
      function expandVisibleFrontier(node: DocumentTreeNode) {
        if (!node.children || node.children.length === 0) return;
        if (current.has(node.path)) {
          next.delete(node.path);
          return;
        }
        node.children.forEach(expandVisibleFrontier);
      }
      expandVisibleFrontier(normalizedRoot);
      return { docSlug: slug, paths: next };
    });
  };

  const handleCollapseToChapters = () => {
    if (!normalizedRoot) return;
    const slug = treeData?.doc_slug || '';
    const set = new Set<string>();
    function walk(node: DocumentTreeNode, depth: number) {
      if (depth >= 1 && node.children && node.children.length > 0) {
        set.add(node.path);
      }
      if (node.children) {
        node.children.forEach((c) => walk(c, depth + 1));
      }
    }
    walk(normalizedRoot, 0);
    setCollapsedState({ docSlug: slug, paths: set });
  };

  // Flatten all nodes for fast in-document search and node lookup
  const { allNodes, nodeByPath } = useMemo(() => {
    const list: DocumentTreeNode[] = [];
    const map = new Map<string, DocumentTreeNode>();
    function walk(node: DocumentTreeNode) {
      list.push(node);
      map.set(node.path, node);
      if (node.children) {
        node.children.forEach(walk);
      }
    }
    if (normalizedRoot) walk(normalizedRoot);
    return { allNodes: list, nodeByPath: map };
  }, [normalizedRoot]);

  const activeSelectionPath = selectedPath || normalizedRoot?.path || '';
  const selectedNode = nodeByPath.get(activeSelectionPath) || normalizedRoot || null;

  // Quick search matches inside the current document tree
  const quickMatches = useMemo(() => {
    const q = quickQuery.trim().toLowerCase();
    if (!q) return [] as DocumentTreeNode[];
    return allNodes
      .filter(
        (n) =>
          n.label.toLowerCase().includes(q) ||
          n.path.toLowerCase().includes(q) ||
          (n.verbatim_text && n.verbatim_text.toLowerCase().includes(q))
      )
      .slice(0, 12);
  }, [allNodes, quickQuery]);

  const activeDoc = documents.find((d) => d.doc_slug === activeDocSlug);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-slate-950">
      {/* Minimal Single Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/50 px-5 py-2.5 sm:px-8">
        {/* Document Selector Popover */}
        <div ref={docMenuRef} className="relative">
          <button
            type="button"
            data-testid="explorer-doc-select"
            onClick={() => setIsDocMenuOpen((v) => !v)}
            className="inline-flex items-center gap-2.5 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-1.5 text-xs font-medium text-slate-100 hover:border-slate-600 transition-colors"
          >
            <FileText className="h-3.5 w-3.5 shrink-0 text-brand-400" />
            <span className="max-w-[260px] sm:max-w-[420px] truncate font-semibold">
              {activeDoc ? activeDoc.title : activeDocSlug}
            </span>
            {activeDoc && (
              <span className="rounded-full bg-slate-800 px-2 py-0.5 font-mono text-[10px] tabular-nums text-slate-300">
                {activeDoc.chunk_count} mục
              </span>
            )}
            <ChevronDown
              className={`h-3.5 w-3.5 text-slate-400 transition-transform ${
                isDocMenuOpen ? 'rotate-180' : ''
              }`}
            />
          </button>

          {isDocMenuOpen && (
            <div
              role="listbox"
              aria-label={t('explorer.docSelect')}
              className="absolute left-0 top-full z-40 mt-1.5 w-[min(92vw,480px)] rounded-2xl border border-slate-700 bg-slate-900 p-1.5 shadow-xl"
            >
              {documents.map((doc) => {
                const isCurrent = doc.doc_slug === activeDocSlug;
                return (
                  <button
                    key={doc.doc_slug}
                    type="button"
                    role="option"
                    aria-selected={isCurrent}
                    onClick={() => {
                      onSelectDoc(doc.doc_slug);
                      onSelectPath('');
                      setIsDocMenuOpen(false);
                    }}
                    className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-xs transition-colors ${
                      isCurrent
                        ? 'bg-brand-950/90 font-semibold text-brand-300'
                        : 'text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    <span className="truncate">{doc.title}</span>
                    <span className="shrink-0 font-mono text-[10px] tabular-nums text-slate-400">
                      {doc.chunk_count} mục
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Quick Search in Mind Map + Global Grep */}
        <div className="flex items-center gap-2">
          <div className="relative w-56 sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={quickQuery}
              onChange={(e) => setQuickQuery(e.target.value)}
              placeholder="Tìm nhanh Điều, Khoản trên sơ đồ…"
              aria-label="Tìm nhanh Điều, Khoản trên sơ đồ"
              className="w-full rounded-xl border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-7 text-xs text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none"
            />
            {quickQuery && (
              <button
                type="button"
                onClick={() => setQuickQuery('')}
                aria-label="Xóa từ khóa tìm nhanh"
                className="absolute right-2 top-1.5 rounded p-0.5 text-slate-400 hover:text-slate-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}

            {/* Instant Jump Dropdown */}
            {quickQuery.trim() && (
              <div className="absolute right-0 top-full z-40 mt-1.5 max-h-80 w-80 sm:w-96 overflow-y-auto overscroll-contain rounded-2xl border border-slate-700 bg-slate-900 p-1.5 shadow-xl">
                {quickMatches.length === 0 ? (
                  <div className="px-3 py-4 text-center text-xs text-slate-400">
                    Không tìm thấy mục nào khớp &ldquo;{quickQuery}&rdquo; trong văn bản này.
                  </div>
                ) : (
                  quickMatches.map((match) => (
                    <button
                      key={match.path}
                      type="button"
                      onClick={() => {
                        handleSelectAndExpand(match.path);
                        setQuickQuery('');
                      }}
                      className="flex w-full flex-col gap-0.5 rounded-xl px-3 py-2 text-left hover:bg-slate-800 transition-colors"
                    >
                      <span className="truncate text-xs font-semibold text-slate-100">
                        {match.label.replace(/^#+\s*/, '')}
                      </span>
                      {match.verbatim_text && (
                        <span className="line-clamp-1 text-[11px] text-slate-400">
                          {match.verbatim_text.replace(/^#+\s*.*\n?/, '').trim()}
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={onOpenGlobalGrep}
            className="hidden md:inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-600 hover:text-slate-100 transition-colors"
            title="Tìm trên toàn bộ kho văn bản (Ctrl+K)"
          >
            <span>Toàn kho (Ctrl+K)</span>
          </button>

          <button
            type="button"
            onClick={onRefresh}
            aria-label={t('explorer.refresh')}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-950 p-1.5 text-xs text-slate-300 hover:border-slate-600 hover:text-slate-100 transition-colors"
            title={t('explorer.refresh')}
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Main Split Workspace: Interactive Mind Map + Clean Reading Drawer */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 h-full min-w-0 overflow-hidden">
          <MindMapCanvas
            rootNode={normalizedRoot}
            selectedPath={activeSelectionPath}
            onSelectPath={handleSelectAndExpand}
            collapsedPaths={collapsedPaths}
            onToggleCollapse={handleToggleCollapse}
            onExpandOneLevel={handleExpandOneLevel}
            onCollapseToChapters={handleCollapseToChapters}
            edges={graphData?.edges || []}
          />
        </div>

        {isInspectorOpen && selectedNode && (
          <div className="w-full sm:w-[400px] lg:w-[440px] xl:w-[480px] shrink-0 h-full overflow-hidden">
            <NodeInspectorPanel
              rootNode={normalizedRoot}
              selectedNode={selectedNode}
              onClose={() => setIsInspectorOpen(false)}
              onSelectPath={handleSelectAndExpand}
              edges={graphData?.edges || []}
            />
          </div>
        )}
      </div>
    </div>
  );
};
