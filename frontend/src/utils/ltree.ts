/**
 * Utility functions for LTree path manipulation, classification, and breadcrumb decomposition.
 */

export interface PathSegment {
  key: string;
  label: string;
  type: string;
  fullPath: string;
}

export function parseLTreePath(path: string): PathSegment[] {
  if (!path) return [];
  const parts = path.split('.');
  const segments: PathSegment[] = [];

  let accumulated = '';
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    accumulated = i === 0 ? part : `${accumulated}.${part}`;

    let label = part;
    let type = 'NODE';

    if (i === 0) {
      label = part.replace(/_/g, '/').toUpperCase();
      type = 'DOCUMENT';
    } else if (part.startsWith('c_') && !part.includes('a_')) {
      const roman = part.substring(2).toUpperCase();
      label = `Chương ${roman}`;
      type = 'CHAPTER';
    } else if (part.startsWith('s_')) {
      const sec = part.substring(2);
      label = `Mục ${sec}`;
      type = 'SECTION';
    } else if (part.startsWith('a_')) {
      const art = part.substring(2);
      label = `Điều ${art}`;
      type = 'ARTICLE';
    } else if (part.startsWith('c_')) {
      const clause = part.substring(2);
      label = `Khoản ${clause}`;
      type = 'CLAUSE';
    } else if (part.startsWith('p_')) {
      const point = part.substring(2);
      label = `Điểm ${point}`;
      type = 'POINT';
    } else if (part.startsWith('app_')) {
      const app = part.substring(4);
      label = `Phụ lục ${app}`;
      type = 'APPENDIX';
    }

    segments.push({
      key: part,
      label,
      type,
      fullPath: accumulated,
    });
  }

  return segments;
}

export function getNodeTypeFromPath(path: string): string {
  const parts = path.split('.');
  if (parts.length === 0) return 'DOCUMENT';
  const last = parts[parts.length - 1];
  if (last.startsWith('p_')) return 'POINT';
  if (parts.length > 2 && last.startsWith('c_')) return 'CLAUSE';
  if (last.startsWith('a_')) return 'ARTICLE';
  if (last.startsWith('s_')) return 'SECTION';
  if (parts.length === 2 && last.startsWith('c_')) return 'CHAPTER';
  if (last.startsWith('app_')) return 'APPENDIX';
  return 'DOCUMENT';
}

export function getNodeTypeColor(nodeType: string): {
  bg: string;
  text: string;
  border: string;
  badge: string;
} {
  switch (nodeType.toUpperCase()) {
    case 'DOCUMENT':
      return {
        bg: 'bg-slate-900',
        text: 'text-slate-100',
        border: 'border-slate-700',
        badge: 'bg-slate-800 text-slate-300 border-slate-700',
      };
    case 'CHAPTER':
      return {
        bg: 'bg-indigo-950/40',
        text: 'text-indigo-300',
        border: 'border-indigo-800/60',
        badge: 'bg-indigo-900/50 text-indigo-300 border-indigo-700',
      };
    case 'SECTION':
      return {
        bg: 'bg-cyan-950/40',
        text: 'text-cyan-300',
        border: 'border-cyan-800/60',
        badge: 'bg-cyan-900/50 text-cyan-300 border-cyan-700',
      };
    case 'ARTICLE':
      return {
        bg: 'bg-emerald-950/40',
        text: 'text-emerald-300',
        border: 'border-emerald-800/60',
        badge: 'bg-emerald-900/50 text-emerald-300 border-emerald-700',
      };
    case 'CLAUSE':
      return {
        bg: 'bg-amber-950/40',
        text: 'text-amber-300',
        border: 'border-amber-800/60',
        badge: 'bg-amber-900/50 text-amber-300 border-amber-700',
      };
    case 'POINT':
      return {
        bg: 'bg-sky-950/40',
        text: 'text-sky-300',
        border: 'border-sky-800/60',
        badge: 'bg-sky-900/50 text-sky-300 border-sky-700',
      };
    case 'APPENDIX':
      return {
        bg: 'bg-purple-950/40',
        text: 'text-purple-300',
        border: 'border-purple-800/60',
        badge: 'bg-purple-900/50 text-purple-300 border-purple-700',
      };
    default:
      return {
        bg: 'bg-slate-900',
        text: 'text-slate-300',
        border: 'border-slate-800',
        badge: 'bg-slate-800 text-slate-400 border-slate-700',
      };
  }
}
