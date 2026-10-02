/**
 * Formatting utilities for Vietnamese currency, legal citations, and timestamps.
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
    case 'MODIFIES_AND_REPLACES':
      return {
        bg: 'bg-purple-950/40',
        text: 'text-purple-300',
        border: 'border-purple-700',
        badge: 'bg-purple-900/60 text-purple-200 border-purple-600',
        label: 'Sửa đổi & Thay thế',
      };
    case 'SANCTIONS':
    case 'DEFINES_SANCTION_FOR':
      return {
        bg: 'bg-rose-950/40',
        text: 'text-rose-300',
        border: 'border-rose-700',
        badge: 'bg-rose-900/60 text-rose-200 border-rose-600',
        label: 'Xử phạt',
      };
    case 'HAS_ADDITIONAL_SANCTION':
      return {
        bg: 'bg-orange-950/40',
        text: 'text-orange-300',
        border: 'border-orange-700',
        badge: 'bg-orange-900/60 text-orange-200 border-orange-600',
        label: 'Hình thức phạt bổ sung',
      };
    case 'REFERENCES':
    case 'REFERENCES_TECHNICAL_STANDARD':
      return {
        bg: 'bg-blue-950/40',
        text: 'text-blue-300',
        border: 'border-blue-700',
        badge: 'bg-blue-900/60 text-blue-200 border-blue-600',
        label: 'Dẫn chiếu Quy chuẩn / Văn bản',
      };
    case 'OVERRIDES':
    case 'OVERRIDES_PRIORITY':
      return {
        bg: 'bg-emerald-950/40',
        text: 'text-emerald-300',
        border: 'border-emerald-700',
        badge: 'bg-emerald-900/60 text-emerald-200 border-emerald-600',
        label: 'Ghi đè Thứ bậc Ưu tiên',
      };
    case 'EXEMPTS':
    case 'EXEMPTS_CONDITION':
      return {
        bg: 'bg-teal-950/40',
        text: 'text-teal-300',
        border: 'border-teal-700',
        badge: 'bg-teal-900/60 text-teal-200 border-teal-600',
        label: 'Miễn trừ / Đặc cách',
      };
    case 'GUIDES':
      return {
        bg: 'bg-indigo-950/40',
        text: 'text-indigo-300',
        border: 'border-indigo-700',
        badge: 'bg-indigo-900/60 text-indigo-200 border-indigo-600',
        label: 'Hướng dẫn thi hành',
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
