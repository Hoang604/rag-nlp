import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextValue {
  showToast: (type: ToastType, title: string, message?: string, duration?: number) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (type: ToastType, title: string, message?: string, duration = 4000) => {
      const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const newToast: ToastItem = { id, type, title, message, duration };
      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback((t: string, m?: string) => showToast('success', t, m), [showToast]);
  const error = useCallback((t: string, m?: string) => showToast('error', t, m, 6000), [showToast]);
  const info = useCallback((t: string, m?: string) => showToast('info', t, m), [showToast]);
  const warning = useCallback((t: string, m?: string) => showToast('warning', t, m, 5000), [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning }}>
      {children}
      {/* Toast Overlay Container */}
      <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-md w-full pointer-events-none">
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success';
          const isError = toast.type === 'error';
          const isWarning = toast.type === 'warning';

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-2xl backdrop-blur-md transition-all duration-200 animate-slide-up ${
                isSuccess
                  ? 'border-emerald-700/70 bg-emerald-950/95 text-emerald-100 shadow-emerald-950/50'
                  : isError
                  ? 'border-rose-700/70 bg-rose-950/95 text-rose-100 shadow-rose-950/50'
                  : isWarning
                  ? 'border-amber-700/70 bg-amber-950/95 text-amber-100 shadow-amber-950/50'
                  : 'border-slate-700 bg-slate-900/95 text-slate-100 shadow-slate-950/50'
              }`}
            >
              <div className="shrink-0 mt-0.5">
                {isSuccess && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
                {isError && <XCircle className="h-5 w-5 text-rose-400" />}
                {isWarning && <AlertCircle className="h-5 w-5 text-amber-400" />}
                {!isSuccess && !isError && !isWarning && <Info className="h-5 w-5 text-blue-400" />}
              </div>

              <div className="flex-1 min-w-0">
                <h4 className="text-xs font-bold leading-tight">{toast.title}</h4>
                {toast.message && (
                  <p className="mt-1 text-[11px] opacity-90 leading-relaxed break-words whitespace-pre-wrap">
                    {toast.message}
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="shrink-0 rounded p-1 opacity-70 hover:opacity-100 hover:bg-white/10 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
