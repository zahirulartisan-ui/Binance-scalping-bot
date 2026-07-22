import React from "react";
import { AlertTriangle, ShieldAlert, CheckCircle2, X } from "lucide-react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "warning" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div
        className="bg-slate-900 border border-slate-700/80 rounded-xl max-w-md w-full shadow-2xl p-6 text-slate-100 relative animate-in zoom-in-95"
        role="dialog"
        aria-modal="true"
      >
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          <div
            className={`p-3 rounded-xl border ${
              variant === "danger"
                ? "bg-rose-950/60 border-rose-500/40 text-rose-400"
                : variant === "warning"
                ? "bg-amber-950/60 border-amber-500/40 text-amber-400"
                : "bg-sky-950/60 border-sky-500/40 text-sky-400"
            }`}
          >
            {variant === "danger" ? (
              <ShieldAlert className="w-6 h-6" />
            ) : (
              <AlertTriangle className="w-6 h-6" />
            )}
          </div>

          <div className="flex-1">
            <h3 className="text-lg font-bold text-slate-100">{title}</h3>
            <p className="mt-2 text-sm text-slate-300 leading-relaxed">{description}</p>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg transition disabled:opacity-50 ${
              variant === "danger"
                ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/50"
                : variant === "warning"
                ? "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-950/50"
                : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50"
            }`}
          >
            {isLoading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <CheckCircle2 className="w-4 h-4" />
            )}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
