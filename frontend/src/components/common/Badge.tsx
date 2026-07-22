import React from "react";

interface BadgeProps {
  text: string;
  variant?:
    | "regime"
    | "permission"
    | "direction"
    | "setup_state"
    | "default";
  size?: "sm" | "md" | "lg";
}

export const Badge: React.FC<BadgeProps> = ({ text, variant = "default", size = "md" }) => {
  const normalized = text?.toUpperCase() || "";

  let classes = "bg-slate-800 text-slate-300 border-slate-700";

  if (variant === "direction") {
    if (normalized === "LONG") {
      classes = "bg-emerald-950/70 text-emerald-300 border-emerald-500/50 font-bold";
    } else if (normalized === "SHORT") {
      classes = "bg-rose-950/70 text-rose-300 border-rose-500/50 font-bold";
    } else {
      classes = "bg-slate-800/80 text-slate-400 border-slate-700";
    }
  } else if (variant === "permission") {
    if (normalized === "ALLOW_LONG" || normalized === "ALLOW_BOTH") {
      classes = "bg-emerald-950/70 text-emerald-300 border-emerald-500/50";
    } else if (normalized === "ALLOW_SHORT") {
      classes = "bg-amber-950/70 text-amber-300 border-amber-500/50";
    } else if (normalized === "BLOCK_NEW_ENTRIES") {
      classes = "bg-rose-950/80 text-rose-300 border-rose-500/60 font-semibold animate-pulse";
    }
  } else if (variant === "regime") {
    if (normalized === "TRENDING_BULLISH") {
      classes = "bg-emerald-950/80 text-emerald-300 border-emerald-500/50";
    } else if (normalized === "TRENDING_BEARISH") {
      classes = "bg-rose-950/80 text-rose-300 border-rose-500/50";
    } else if (normalized === "RANGING") {
      classes = "bg-sky-950/80 text-sky-300 border-sky-500/50";
    } else if (normalized === "HIGH_VOLATILITY") {
      classes = "bg-amber-950/80 text-amber-300 border-amber-500/50";
    } else if (normalized === "ABNORMAL_MARKET" || normalized === "NO_TRADE") {
      classes = "bg-rose-950/90 text-rose-200 border-rose-500/70 font-semibold";
    } else {
      classes = "bg-slate-800 text-slate-400 border-slate-700";
    }
  } else if (variant === "setup_state") {
    if (normalized === "READY") {
      classes = "bg-emerald-950/90 text-emerald-300 border-emerald-500/60 font-bold shadow-sm shadow-emerald-900/30";
    } else if (normalized === "FORMING") {
      classes = "bg-sky-950/80 text-sky-300 border-sky-500/50";
    } else if (normalized === "INVALIDATED" || normalized === "EXPIRED") {
      classes = "bg-slate-900 text-slate-400 border-slate-800";
    } else if (normalized === "BLOCKED_BY_REGIME") {
      classes = "bg-purple-950/80 text-purple-300 border-purple-500/50 font-semibold";
    } else {
      classes = "bg-slate-800 text-slate-400 border-slate-700";
    }
  }

  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[11px]"
      : size === "lg"
      ? "px-3 py-1.5 text-xs font-semibold"
      : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center justify-center rounded-md border ${sizeClasses} ${classes} font-mono tracking-tight uppercase whitespace-nowrap`}
    >
      {text.replace(/_/g, " ")}
    </span>
  );
};
