import React from "react";

interface StatusChipProps {
  label: string;
  value?: string;
  statusKey?: string;
  size?: "sm" | "md";
}

export const StatusChip: React.FC<StatusChipProps> = ({
  label,
  value,
  statusKey,
  size = "md",
}) => {
  const normalized = (value || statusKey || label).toString().toLowerCase();

  let colorClasses = "bg-slate-800/80 text-slate-300 border-slate-700/60";
  let dotColor = "bg-slate-400";

  // Green: ok, ready, enabled, inactive (emergency stop inactive is GOOD)
  if (
    normalized === "ok" ||
    normalized === "ready" ||
    normalized === "enabled" ||
    normalized === "inactive" ||
    normalized === "completed"
  ) {
    colorClasses = "bg-emerald-950/50 text-emerald-300 border-emerald-500/40";
    dotColor = "bg-emerald-400";
  }
  // Red: error, not_ready, active (emergency stop active is EMERGENCY/CRITICAL), failed
  else if (
    normalized === "error" ||
    normalized === "not_ready" ||
    normalized === "active" ||
    normalized === "failed"
  ) {
    colorClasses = "bg-rose-950/60 text-rose-300 border-rose-500/50";
    dotColor = "bg-rose-400 animate-pulse";
  }
  // Amber / Orange: partial_failure, warning, started
  else if (normalized === "partial_failure" || normalized === "warning" || normalized === "started") {
    colorClasses = "bg-amber-950/50 text-amber-300 border-amber-500/40";
    dotColor = "bg-amber-400";
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border ${padding} ${colorClasses} tracking-tight font-mono transition-colors`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span className="text-slate-400 uppercase text-[10px] tracking-wider font-semibold mr-0.5">{label}:</span>
      <span className="font-semibold uppercase">{value || statusKey}</span>
    </span>
  );
};
