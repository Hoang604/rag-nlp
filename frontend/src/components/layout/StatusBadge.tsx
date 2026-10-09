import React from 'react';
import { Database } from 'lucide-react';

interface StatusBadgeProps {
  status?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status = 'POSTGRESQL LIVE',
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5 font-medium',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border border-emerald-600/50 bg-emerald-950/60 text-emerald-300 ${sizeClasses[size]}`}
    >
      <Database className="w-3.5 h-3.5 text-emerald-400" />
      <span>{status}</span>
    </span>
  );
};
