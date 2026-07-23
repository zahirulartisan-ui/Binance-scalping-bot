import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/client";
import { useSymbol } from "../../context/SymbolContext";
import { useTabVisibility } from "../../hooks/useTabVisibility";
import {
  ShieldAlert,
  Activity,
  Coins,
  RefreshCw,
  Radio,
  Server,
  Menu,
} from "lucide-react";

export const TopBar: React.FC<{ onMenuClick?: () => void }> = ({ onMenuClick }) => {
  const { selectedSymbol, setSelectedSymbol, symbols, isLoadingSymbols } = useSymbol();
  const isTabVisible = useTabVisibility();

  // Poll health & settings every 15s (paused if tab is hidden)
  const { data: health, isLoading: isLoadingHealth, refetch: refetchHealth, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: isTabVisible ? 15000 : false,
  });

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiClient.getSettings(),
    refetchInterval: isTabVisible ? 15000 : false,
  });

  const isEmergencyStopActive =
    health?.emergency_stop?.status === "active" || settings?.emergency_stop === true;

  const appEnv = health?.environment?.status || "";

  const isHealthOk = health?.application?.status === "ok";

  return (
    <header className="h-16 bg-slate-950/90 border-b border-slate-800/80 px-6 flex items-center justify-between sticky top-0 z-20 backdrop-blur-md">
      {/* Left: Health & Environment Indicators */}
      <div className="flex items-center gap-3">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100 transition"
            title="Open Navigation Menu"
          >
            <Menu className="w-4.5 h-4.5" />
          </button>
        )}

        {/* Health status indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
          <Activity
            className={`w-3.5 h-3.5 ${
              isLoadingHealth
                ? "text-slate-400 animate-spin"
                : isHealthOk
                ? "text-emerald-400"
                : "text-rose-400"
            }`}
          />
          <span className="text-slate-400 font-medium">Health:</span>
          <span
            className={`font-semibold ${
              isHealthOk ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {isLoadingHealth ? "CONNECTING..." : isHealthOk ? "ONLINE" : "ERROR"}
          </span>
        </div>

        {/* Environment Badge */}
        {appEnv && (
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-xs font-mono">
            <Server className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400">ENV:</span>
            <span className="text-sky-300 font-semibold uppercase">{appEnv}</span>
          </div>
        )}

        {/* Emergency Stop Badge */}
        {isEmergencyStopActive ? (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-rose-600 text-white border border-rose-400 text-xs font-mono font-bold animate-pulse shadow-lg shadow-rose-950/80">
            <ShieldAlert className="w-4 h-4" />
            <span>EMERGENCY STOP ACTIVE</span>
          </div>
        ) : (
          health?.execution?.status !== "disabled" && (
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
              <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
              <span>SYSTEM ACTIVE</span>
            </div>
          )
        )}

        {/* Execution Off Badge */}
        {health?.execution?.status === "disabled" && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-400 text-xs font-mono">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            <span>EXECUTION OFF</span>
          </div>
        )}

        {/* Demo Off Badge */}
        {health?.demo_trading?.status === "disabled" && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs font-mono">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <span>DEMO OFF</span>
          </div>
        )}
      </div>

      {/* Right: Symbol Picker & Manual Refetch */}
      <div className="flex items-center gap-3">
        {/* Symbol Dropdown */}
        <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
          <Coins className="w-4 h-4 text-amber-400" />
          <label htmlFor="symbol-picker" className="text-xs font-mono text-slate-400 font-medium hidden sm:inline">
            Symbol:
          </label>
          <select
            id="symbol-picker"
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            disabled={isLoadingSymbols}
            className="bg-transparent text-slate-100 font-mono text-xs font-bold focus:outline-none cursor-pointer"
          >
            {symbols.map((sym) => (
              <option key={sym.symbol} value={sym.symbol} className="bg-slate-900 text-slate-100">
                {sym.symbol} ({sym.base_asset}/{sym.quote_asset})
              </option>
            ))}
          </select>
        </div>

        {/* Manual Refetch Trigger */}
        <button
          onClick={() => refetchHealth()}
          disabled={isFetching}
          className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-100 hover:border-slate-700 transition font-mono text-xs flex items-center gap-1.5"
          title="Refresh connection status"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin text-amber-400" : ""}`} />
        </button>
      </div>
    </header>
  );
};
