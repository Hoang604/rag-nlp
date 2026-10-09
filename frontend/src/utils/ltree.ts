/**
 * Utility functions for LTree path manipulation, classification, and breadcrumb decomposition.
 */

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
    case 'SECTION':
      return {
        bg: 'bg-indigo-950/40',
        text: 'text-indigo-200',
        border: 'border-indigo-800/60',
        badge: 'bg-indigo-900/60 text-indigo-300 border-indigo-700',
      };
    case 'TABLE':
      return {
        bg: 'bg-emerald-950/40',
        text: 'text-emerald-200',
        border: 'border-emerald-800/60',
        badge: 'bg-emerald-900/60 text-emerald-300 border-emerald-700',
      };
    case 'CODE':
      return {
        bg: 'bg-amber-950/40',
        text: 'text-amber-200',
        border: 'border-amber-800/60',
        badge: 'bg-amber-900/60 text-amber-300 border-amber-700',
      };
    case 'LIST':
      return {
        bg: 'bg-purple-950/40',
        text: 'text-purple-200',
        border: 'border-purple-800/60',
        badge: 'bg-purple-900/60 text-purple-300 border-purple-700',
      };
    case 'PARAGRAPH':
    default:
      return {
        bg: 'bg-slate-900/60',
        text: 'text-slate-200',
        border: 'border-slate-800',
        badge: 'bg-slate-800/80 text-slate-300 border-slate-700',
      };
  }
}
