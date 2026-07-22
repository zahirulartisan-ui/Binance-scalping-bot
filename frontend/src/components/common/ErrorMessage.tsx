import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorMessageProps {
  title?: string;
  message?: string;
  error?: Error | null | any;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = "Backend Service Offline",
  message = "Could not connect to the Binance scalping bot backend. Please make sure the FastAPI engine is running and reachable.",
  error,
  onRetry,
  isRetrying = false,
}) => {
  const getErrorDetail = () => {
    if (!error) return null;
    if (error instanceof Error) return error.message;
    if (typeof error === "string") return error;
    if (typeof error === "object") {
      try {
        return JSON.stringify(error);
      } catch {
        return "Unknown error object";
      }
    }
    return "Unknown error";
  };

  const errorDetail = getErrorDetail();

  return (
    <div className="border border-rose-500/30 bg-rose-950/20 rounded-xl p-5 md:p-6 text-slate-300 font-mono text-sm shadow-lg max-w-2xl mx-auto space-y-4">
      <div className="flex items-start gap-3.5">
        <div className="p-2 bg-rose-950/60 border border-rose-500/40 rounded-lg text-rose-400 shrink-0">
          <AlertCircle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <h4 className="text-base font-bold text-rose-200 tracking-tight">
            {title}
          </h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            {message}
          </p>
        </div>
      </div>

      {errorDetail && (
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3 text-xs text-rose-300/90 font-mono overflow-x-auto max-h-32 whitespace-pre-wrap">
          <span className="text-slate-500 font-bold block mb-1">ERROR DETAILS:</span>
          {errorDetail}
        </div>
      )}

      <div className="flex items-center justify-between gap-4 pt-1.5 border-t border-slate-800/60">
        <span className="text-[11px] text-slate-500">
          Status: <span className="text-rose-400 font-semibold uppercase">Offline</span>
        </span>
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={isRetrying}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/40 text-rose-300 border border-rose-500/30 hover:border-rose-500/50 rounded-lg text-xs font-bold transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? "animate-spin" : ""}`} />
            {isRetrying ? "Retrying..." : "Retry Connection"}
          </button>
        )}
      </div>
    </div>
  );
};
