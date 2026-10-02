import React from 'react';
import { CheckCircle2, Clock, Eye, Sparkles } from 'lucide-react';
import { StagingStatus } from '../../types/staging';

interface StatusBadgeProps {
  status: StagingStatus;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-medium',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  switch (status) {
    case 'DRAFT':
      return (
        <span
          className={`inline-flex items-center rounded-full border border-slate-700 bg-slate-800/80 text-slate-300 ${sizeClasses[size]}`}
        >
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>DRAFT (Bản Nháp)</span>
        </span>
      );
    case 'AGENT_COMMITTED':
      return (
        <span
          className={`inline-flex items-center rounded-full border border-blue-600/50 bg-blue-950/60 text-blue-300 ${sizeClasses[size]}`}
        >
          <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
          <span>AGENT COMMITTED (AI Đã Xử Lý)</span>
        </span>
      );
    case 'APPROVED':
      return (
        <span
          className={`inline-flex items-center rounded-full border border-emerald-600/50 bg-emerald-950/60 text-emerald-300 ${sizeClasses[size]}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>APPROVED (Đã Phê Duyệt)</span>
        </span>
      );
    case 'PROMOTED':
      return (
        <span
          className={`inline-flex items-center rounded-full border border-purple-600/50 bg-purple-950/60 text-purple-200 ${sizeClasses[size]}`}
        >
          <Eye className="w-3.5 h-3.5 text-purple-400" />
          <span>PROMOTED (Đã Nhập CSDL)</span>
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center rounded-full border border-slate-700 bg-slate-800 text-slate-400 ${sizeClasses[size]}`}
        >
          <span>{status}</span>
        </span>
      );
  }
};
