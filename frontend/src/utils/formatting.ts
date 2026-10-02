/**
 * Formatting utilities for dates, numbers, timestamps, and relation badges.
 */


export function formatISODate(dateStr?: string | null): string {
  if (!dateStr) return 'Không thời hạn';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export function formatISODateTime(dateTimeStr?: string | null): string {
  if (!dateTimeStr) return '—';
  try {
    const d = new Date(dateTimeStr);
    if (isNaN(d.getTime())) return dateTimeStr;
    return d.toLocaleString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return dateTimeStr;
  }
}

export function getRelationColor(relationType: string): {
  bg: string;
  text: string;
  border: string;
  badge: string;
  label: string;
} {
  switch (relationType.toUpperCase()) {
    case 'REFERENCES':
      return {
        bg: 'bg-blue-950/40',
        text: 'text-blue-300',
        border: 'border-blue-700',
        badge: 'bg-blue-900/60 text-blue-200 border-blue-600',
        label: 'Tham chiếu / Dẫn nguồn (REFERENCES)',
      };
    case 'SUPPORTS':
      return {
        bg: 'bg-emerald-950/40',
        text: 'text-emerald-300',
        border: 'border-emerald-700',
        badge: 'bg-emerald-900/60 text-emerald-200 border-emerald-600',
        label: 'Bổ trợ / Củng cố luận điểm (SUPPORTS)',
      };
    case 'CONTRADICTS':
      return {
        bg: 'bg-rose-950/40',
        text: 'text-rose-300',
        border: 'border-rose-700',
        badge: 'bg-rose-900/60 text-rose-200 border-rose-600',
        label: 'Mâu thuẫn / Phản bác (CONTRADICTS)',
      };
    case 'DEFINES':
      return {
        bg: 'bg-purple-950/40',
        text: 'text-purple-300',
        border: 'border-purple-700',
        badge: 'bg-purple-900/60 text-purple-200 border-purple-600',
        label: 'Định nghĩa / Khái niệm (DEFINES)',
      };
    case 'EXTENDS':
      return {
        bg: 'bg-indigo-950/40',
        text: 'text-indigo-300',
        border: 'border-indigo-700',
        badge: 'bg-indigo-900/60 text-indigo-200 border-indigo-600',
        label: 'Mở rộng / Phát triển thêm (EXTENDS)',
      };
    case 'EXEMPLIFIES':
      return {
        bg: 'bg-amber-950/40',
        text: 'text-amber-300',
        border: 'border-amber-700',
        badge: 'bg-amber-900/60 text-amber-200 border-amber-600',
        label: 'Ví dụ minh họa (EXEMPLIFIES)',
      };
    case 'DEPENDS_ON':
      return {
        bg: 'bg-cyan-950/40',
        text: 'text-cyan-300',
        border: 'border-cyan-700',
        badge: 'bg-cyan-900/60 text-cyan-200 border-cyan-600',
        label: 'Phụ thuộc điều kiện (DEPENDS_ON)',
      };
    case 'SUPERSEDES':
      return {
        bg: 'bg-red-950/40',
        text: 'text-red-300',
        border: 'border-red-700',
        badge: 'bg-red-900/60 text-red-200 border-red-600',
        label: 'Thay thế / Bãi bỏ (SUPERSEDES)',
      };
    case 'SEE_ALSO':
      return {
        bg: 'bg-slate-900',
        text: 'text-slate-300',
        border: 'border-slate-700',
        badge: 'bg-slate-800 text-slate-300 border-slate-600',
        label: 'Tham khảo thêm (SEE_ALSO)',
      };
    default:
      return {
        bg: 'bg-slate-900',
        text: 'text-slate-300',
        border: 'border-slate-700',
        badge: 'bg-slate-800 text-slate-300 border-slate-600',
        label: relationType,
      };
  }
}
