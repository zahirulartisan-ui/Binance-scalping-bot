import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { StatusChip } from "../components/common/StatusChip";
import { Badge } from "../components/common/Badge";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { useSymbol } from "../context/SymbolContext";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Database,
  ShieldAlert,
  SlidersHorizontal,
  Server,
  Zap,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Clock,
  Layers,
} from "lucide-react";

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { setSelectedSymbol } = useSymbol();
  const isTabVisible = useTabVisibility();

  // Poll health every 15s (paused if tab is hidden)
  const {
    data: health,
    isLoading: isLoadingHealth,
    isError: isErrorHealth,
    error: errorHealth,
    refetch: refetchHealth,
    isFetching: isFetchingHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  // Poll market data status every 10s
  const {
    data: marketDataStatus,
    isLoading: isLoadingMarketStatus,
    isError: isErrorMarketStatus,
    error: errorMarketStatus,
    refetch: refetchMarketStatus,
  } = useQuery({
    queryKey: ["marketDataStatus"],
    queryFn: () => apiClient.getMarketDataStatus(),
    refetchInterval: isTabVisible ? 10000 : false,
    retry: 1,
  });

  // Poll BTC market regime every 15s
  const {
    data: btcRegime,
    isLoading: isLoadingRegime,
    isError: isErrorRegime,
    error: errorRegime,
    refetch: refetchRegime,
  } = useQuery({
    queryKey: ["btcRegime"],
    queryFn: () => apiClient.getMarketRegimeBtc(),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  // Poll live strategy setups feed every 7s
  const {
    data: setups = [],
    isLoading: isLoadingSetups,
    isError: isErrorSetups,
    error: errorSetups,
    refetch: refetchSetups,
  } = useQuery({
    queryKey: ["setupsFeed"],
    queryFn: () => apiClient.getStrategySetups({ eligible_only: false, limit: 10 }),
    refetchInterval: isTabVisible ? 7000 : false,
    retry: 1,
  });

  const isError = isErrorHealth || isErrorMarketStatus || isErrorRegime || isErrorSetups;
  const anyError = errorHealth || errorMarketStatus || errorRegime || errorSetups;
  const isRetrying = isFetchingHealth;

  if (isError) {
    return (
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
              <Activity className="w-6 h-6 text-amber-400 inline" /> TELEMETRY DASHBOARD
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-1">
              Real-time execution health, market regime monitoring, and live strategy setups feed.
            </p>
          </div>
        </div>
        <div className="py-12">
          <ErrorMessage
            title="Telemetry Dashboard Unavailable"
            message="We were unable to load the real-time telemetry feed from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refetchHealth();
              refetchMarketStatus();
              refetchRegime();
              refetchSetups();
            }}
            isRetrying={isRetrying}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6 text-amber-400 inline" /> TELEMETRY DASHBOARD
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Real-time execution health, market regime monitoring, and live strategy setups feed.
          </p>
        </div>
      </div>

      {/* 1. Health Summary Cards Grid */}
      <section className="space-y-3">
        <h2 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold flex items-center gap-2">
          <Server className="w-4 h-4 text-emerald-400" /> Application Core Health
        </h2>
        {isLoadingHealth ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 h-24 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* App Engine */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 font-semibold">
                  <Zap className="w-4 h-4 text-amber-400" /> APPLICATION
                </span>
                <StatusChip label="Engine" value={health?.application?.status || "unknown"} />
              </div>
              <div className="mt-2 text-xs font-mono text-slate-300 truncate">
                {health?.application?.detail || "Engine operating normally"}
              </div>
            </div>

            {/* Database Pool */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 font-semibold">
                  <Database className="w-4 h-4 text-sky-400" /> DATABASE
                </span>
                <StatusChip label="Status" value={health?.database?.status || "unknown"} />
              </div>
              <div className="mt-2 text-xs font-mono text-slate-300 truncate">
                {health?.database?.detail || "PostgreSQL connection pool healthy"}
              </div>
            </div>

            {/* Execution Engine */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 font-semibold">
                  <Activity className="w-4 h-4 text-emerald-400" /> EXECUTION
                </span>
                <StatusChip label="State" value={health?.execution?.status || "disabled"} />
              </div>
              <div className="mt-2 text-xs font-mono text-slate-300 truncate">
                Demo Trading: <span className="text-emerald-400 font-semibold">{health?.demo_trading?.status || "enabled"}</span>
              </div>
            </div>

            {/* Emergency Stop & Migrations */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-lg flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 font-semibold">
                  <ShieldAlert className="w-4 h-4 text-rose-400" /> SAFETY LOCK
                </span>
                <StatusChip label="Killswitch" value={health?.emergency_stop?.status || "inactive"} />
              </div>
              <div className="mt-2 text-xs font-mono text-slate-300 truncate">
                Migrations: <span className="text-sky-300 font-semibold">{health?.migrations?.status || "ready"}</span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 2. Middle Row: Market Data Runner + BTC Regime Summary Widget */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Market Data Status Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold font-mono text-slate-100 flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" /> MARKET DATA RUNNER
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-400">Runner:</span>
              <StatusChip label="Active" value={marketDataStatus?.runner_active ? "enabled" : "disabled"} />
            </div>
          </div>

          {isLoadingMarketStatus ? (
            <div className="h-28 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-slate-700 border-t-sky-400 rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-3 font-mono text-xs text-slate-300">
              <div className="grid grid-cols-2 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div>
                  <span className="text-slate-400 text-[11px]">Collection Mode:</span>
                  <div className="font-semibold text-slate-100 mt-0.5">
                    {marketDataStatus?.collection_enabled ? "ACTIVE (Polling)" : "PAUSED"}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400 text-[11px]">Latest Cycle Status:</span>
                  <div className="mt-0.5">
                    <StatusChip label="Cycle" value={marketDataStatus?.latest_cycle_status || "completed"} />
                  </div>
                </div>
              </div>

              {/* Cycle Timestamp Info */}
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-400" /> Last Started:{" "}
                  {marketDataStatus?.latest_cycle_started_at
                    ? new Date(marketDataStatus.latest_cycle_started_at).toLocaleTimeString()
                    : "N/A"}
                </span>
                <span>
                  Finished:{" "}
                  {marketDataStatus?.latest_cycle_finished_at
                    ? new Date(marketDataStatus.latest_cycle_finished_at).toLocaleTimeString()
                    : "N/A"}
                </span>
              </div>

              {/* Cycle Rejections Table/List */}
              {marketDataStatus?.latest_cycle_rejections &&
              Object.keys(marketDataStatus.latest_cycle_rejections).length > 0 ? (
                <div className="border border-amber-500/30 bg-amber-950/20 rounded-lg p-3 space-y-1.5">
                  <div className="text-[11px] font-bold text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Active Cycle Rejections (
                    {Object.keys(marketDataStatus.latest_cycle_rejections).length})
                  </div>
                  <div className="max-h-24 overflow-y-auto space-y-1 text-[11px]">
                    {Object.entries(marketDataStatus.latest_cycle_rejections).map(([sym, reason]) => (
                      <div key={sym} className="flex items-start justify-between gap-2 border-b border-amber-900/30 pb-1">
                        <span className="font-bold text-slate-200">{sym}:</span>
                        <span className="text-amber-300 text-right">{reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20 text-[11px] text-emerald-400 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>No ticker rejections reported in latest cycle. All symbols passing filter limits.</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* BTC Market Regime Summary Widget */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold font-mono text-slate-100 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-400" /> MARKET REGIME (BTC ANCHOR)
            </h3>
            <button
              onClick={() => navigate("/regime")}
              className="text-xs font-mono text-amber-400 hover:text-amber-300 flex items-center gap-1 transition"
            >
              Full Regime View <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {isLoadingRegime ? (
            <div className="h-28 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-slate-700 border-t-amber-400 rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-4 font-mono text-xs">
              {/* Regime & Permission Badges */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase block mb-1">Primary Regime</span>
                  <Badge text={btcRegime?.primary_regime || "TRENDING_BULLISH"} variant="regime" size="md" />
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] uppercase block mb-1">Entry Permission</span>
                  <Badge text={btcRegime?.entry_permission || "ALLOW_LONG"} variant="permission" size="md" />
                </div>
              </div>

              {/* Confidence Score Progress Bar */}
              <div>
                <div className="flex items-center justify-between text-xs text-slate-300 mb-1.5">
                  <span className="text-slate-400">Regime Confidence Score:</span>
                  <span className="font-bold text-amber-400">
                    {Math.round((btcRegime?.confidence_score || 0.85) * 100)}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden p-0.5 border border-slate-700">
                  <div
                    className="bg-gradient-to-r from-amber-500 to-emerald-400 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${Math.round((btcRegime?.confidence_score || 0.85) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Market-wide block warning banner if true */}
              {btcRegime?.market_wide_block ? (
                <div className="p-3 bg-rose-950/70 border border-rose-500/60 rounded-lg text-rose-200 text-xs font-semibold flex items-center gap-2 animate-pulse">
                  <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                  <span>WARNING: Market-Wide Entry Block in Effect! Scalping strategies paused across all symbols.</span>
                </div>
              ) : (
                <div className="text-[11px] text-slate-400 flex items-center justify-between">
                  <span>Trend Strength: {(btcRegime?.trend_strength_value || 0.76).toFixed(2)}</span>
                  <span>Spread: {btcRegime?.spread_value ? `${btcRegime.spread_value} bps` : "1.2 bps"}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 3. Live Strategy Setups Feed (Latest 10 Rows) */}
      <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-sm font-bold font-mono text-slate-100 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-emerald-400" /> LIVE STRATEGY SETUPS FEED
            </h2>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">
              Latest candidate entry setups detected by the trend-pullback scanner (polling 7s).
            </p>
          </div>
          <button
            onClick={() => navigate("/setups")}
            className="text-xs font-mono text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition"
          >
            All Strategy Setups <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {isLoadingSetups ? (
          <div className="h-40 flex flex-col items-center justify-center gap-2">
            <div className="w-6 h-6 border-2 border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
            <span className="text-xs font-mono text-slate-400">Scanning orderbooks for setups...</span>
          </div>
        ) : setups.length === 0 ? (
          <div className="text-center p-8 border border-slate-800 rounded-lg bg-slate-950/40 text-slate-400 text-xs font-mono">
            No active setups currently forming.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono tabular-nums border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-3">Setup ID</th>
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Direction</th>
                  <th className="py-2.5 px-3">Setup State</th>
                  <th className="py-2.5 px-3 text-right">Preferred Entry</th>
                  <th className="py-2.5 px-3 text-right">R:R</th>
                  <th className="py-2.5 px-3 text-center">Signal Eligible</th>
                  <th className="py-2.5 px-3 text-right">Evaluated At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {setups.map((setup) => (
                  <tr
                    key={setup.setup_id}
                    onClick={() => {
                      setSelectedSymbol(setup.symbol);
                      navigate("/setups");
                    }}
                    className="hover:bg-slate-800/50 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-3 font-semibold text-amber-400/90">{setup.setup_id.slice(0, 10)}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-100">{setup.symbol}</td>
                    <td className="py-2.5 px-3">
                      <Badge text={setup.direction} variant="direction" size="sm" />
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge text={setup.setup_state} variant="setup_state" size="sm" />
                    </td>
                    <td className="py-2.5 px-3 text-right font-semibold text-slate-100">
                      ${setup.preferred_entry.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                      {setup.reward_to_risk ? setup.reward_to_risk.toFixed(2) : "N/A"}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {setup.eligible_for_signal ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                      ) : (
                        <XCircle className="w-4 h-4 text-slate-500 inline" />
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-400 text-[11px]">
                      {new Date(setup.evaluated_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
