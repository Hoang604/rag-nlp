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
  if (parts.length <= 1) return 'DOCUMENT';
  return 'NODE';
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
    case 'NODE':
    default:
      return {
        bg: 'bg-slate-900/60',
        text: 'text-slate-200',
        border: 'border-slate-800',
        badge: 'bg-slate-800/80 text-slate-300 border-slate-700',
      };
  }
}
