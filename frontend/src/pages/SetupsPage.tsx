import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { StrategySetup, StrategySetupState } from "../api/types";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { Badge } from "../components/common/Badge";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  SlidersHorizontal,
  Filter,
  CheckCircle2,
  XCircle,
  X,
  RefreshCw,
  Search,
  Activity,
  Layers,
  Sparkles,
  ShieldAlert,
  Info,
  Clock,
  ExternalLink,
} from "lucide-react";

export const SetupsPage: React.FC = () => {
  // Filter state
  const [selectedState, setSelectedState] = useState<string>("ALL");
  const [eligibleOnly, setEligibleOnly] = useState<boolean>(false);
  const [symbolFilter, setSymbolFilter] = useState<string>("");
  const [limit, setLimit] = useState<number>(25);

  const isTabVisible = useTabVisibility();

  // Selected setup for Detail Drawer
  const [activeSetupId, setActiveSetupId] = useState<string | null>(null);
  const [activeSymbol, setActiveSymbol] = useState<string | null>(null);

  // Poll strategy setups table every 7s (paused if tab is hidden)
  const {
    data: setups = [],
    isLoading: isLoadingSetups,
    isError: isErrorSetups,
    error: errorSetups,
    refetch: refetchSetups,
    isFetching: isFetchingSetups,
  } = useQuery({
    queryKey: ["setups", selectedState, eligibleOnly, symbolFilter, limit],
    queryFn: () =>
      apiClient.getStrategySetups({
        state: selectedState,
        eligible_only: eligibleOnly,
        symbol: symbolFilter,
        limit,
      }),
    refetchInterval: isTabVisible ? 7000 : false,
    retry: 1,
  });

  // Query Strategies Info panel
  const {
    data: strategies = [],
    isLoading: isLoadingStrategies,
    isError: isErrorStrategies,
    error: errorStrategies,
    refetch: refetchStrategies,
  } = useQuery({
    queryKey: ["strategiesInfo"],
    queryFn: () => apiClient.getStrategiesInfo(),
    staleTime: 30000,
    retry: 1,
  });

  const isError = isErrorSetups || isErrorStrategies;
  const anyError = errorSetups || errorStrategies;
  const isRetrying = isFetchingSetups;

  // Query Live Evaluation inside Detail Drawer when setup is selected
  const {
    data: liveEval,
    isLoading: isLoadingLiveEval,
    error: liveEvalError,
    refetch: refetchLiveEval,
  } = useQuery({
    queryKey: ["liveEval", activeSymbol],
    queryFn: () => apiClient.getLiveEvaluation(activeSymbol || "BTCUSDT", true),
    enabled: !!activeSymbol,
    retry: false,
  });

  const activeSetup = setups.find((s) => s.setup_id === activeSetupId);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <SlidersHorizontal className="w-6 h-6 text-emerald-400 inline" /> STRATEGY SETUPS MONITOR
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Real-time candidate trade setups from automated scanner engines. Click row to open deep evaluation inspect.
          </p>
        </div>

        <button
          onClick={() => refetchSetups()}
          disabled={isFetchingSetups}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 hover:border-slate-700 font-mono text-xs flex items-center gap-2 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetchingSetups ? "animate-spin text-amber-400" : ""}`} />
          <span>Refresh Setups</span>
        </button>
      </div>

      {isError ? (
        <div className="py-12">
          <ErrorMessage
            title="Strategy Setups Stream Offline"
            message="We were unable to load the active scanner setups feed from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refetchSetups();
              refetchStrategies();
            }}
            isRetrying={isRetrying}
          />
        </div>
      ) : (
        <>
          {/* Strategies Info Panel (Upper Banner) */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
        <div className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
          <Layers className="w-4 h-4 text-sky-400" /> Active Scanner Engines ({strategies.length})
        </div>
        {isLoadingStrategies ? (
          <div className="h-10 flex items-center text-xs font-mono text-slate-400">Loading strategy manifests...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {strategies.map((strat) => (
              <div key={strat.name} className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 flex items-center justify-between font-mono text-xs">
                <div>
                  <div className="font-bold text-slate-100 flex items-center gap-2">
                    {strat.name} <span className="text-[10px] text-slate-400 font-normal">v{strat.version}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Timeframes: Entry ({strat.entry_timeframe}) | Confirm ({strat.confirmation_timeframe}) | Context ({strat.context_timeframe})
                  </div>
                </div>
                <div className="text-right">
                  <Badge text={strat.trading_mode} variant="default" size="sm" />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Filter Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Filter className="w-4 h-4 text-amber-400" />
            <span className="font-semibold text-slate-300">Filters:</span>
          </div>

          {/* Setup State Dropdown */}
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-400 text-[11px]">State:</span>
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer"
            >
              {[
                "ALL",
                "NO_SETUP",
                "FORMING",
                "READY",
                "INVALIDATED",
                "EXPIRED",
                "INSUFFICIENT_DATA",
                "BLOCKED_BY_REGIME",
              ].map((st) => (
                <option key={st} value={st} className="bg-slate-900 text-slate-100">
                  {st}
                </option>
              ))}
            </select>
          </div>

          {/* Symbol search filter */}
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Symbol (e.g. BTC)..."
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              className="bg-transparent text-slate-100 placeholder-slate-500 w-28 focus:outline-none"
            />
          </div>

          {/* Eligible only toggle */}
          <label className="flex items-center gap-2 cursor-pointer bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 select-none">
            <input
              type="checkbox"
              checked={eligibleOnly}
              onChange={(e) => setEligibleOnly(e.target.checked)}
              className="rounded accent-emerald-500 w-3.5 h-3.5 cursor-pointer"
            />
            <span className="text-slate-300 font-medium">Eligible Only</span>
          </label>
        </div>

        {/* Limit Selector */}
        <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 text-[11px]">Limit:</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer"
          >
            {[10, 25, 50, 100].map((num) => (
              <option key={num} value={num} className="bg-slate-900 text-slate-100">
                {num}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Strategy Setups Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
        {isLoadingSetups ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-3 border-slate-700 border-t-emerald-400 rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs font-mono text-slate-400">Loading candidate setups...</p>
          </div>
        ) : setups.length === 0 ? (
          <div className="p-10 text-center font-mono text-xs text-slate-400">
            No strategy setups matching current filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-3">Setup ID</th>
                  <th className="py-3 px-3">Symbol</th>
                  <th className="py-3 px-3">Direction</th>
                  <th className="py-3 px-3">State</th>
                  <th className="py-3 px-3 text-right">Entry Zone</th>
                  <th className="py-3 px-3 text-right">Preferred Entry</th>
                  <th className="py-3 px-3 text-right">Stop Loss</th>
                  <th className="py-3 px-3 text-right">Take Profit</th>
                  <th className="py-3 px-3 text-right">R:R</th>
                  <th className="py-3 px-3 text-center">Sweep</th>
                  <th className="py-3 px-3 text-center">MSS</th>
                  <th className="py-3 px-3 text-center">Eligible</th>
                  <th className="py-3 px-3 text-right">Evaluated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {setups.map((setup) => (
                  <tr
                    key={setup.setup_id}
                    onClick={() => {
                      setActiveSetupId(setup.setup_id);
                      setActiveSymbol(setup.symbol);
                    }}
                    className={`transition-colors hover:bg-slate-800/60 cursor-pointer ${
                      activeSetupId === setup.setup_id ? "bg-slate-800/80 border-l-2 border-l-amber-400" : ""
                    }`}
                  >
                    <td className="py-3 px-3 font-semibold text-amber-400/90">{setup.setup_id.slice(0, 10)}</td>
                    <td className="py-3 px-3 font-bold text-slate-100">{setup.symbol}</td>
                    <td className="py-3 px-3">
                      <Badge text={setup.direction} variant="direction" size="sm" />
                    </td>
                    <td className="py-3 px-3">
                      <Badge text={setup.setup_state} variant="setup_state" size="sm" />
                    </td>
                    <td className="py-3 px-3 text-right text-slate-300 text-[11px]">
                      {setup.entry_zone_low > 0 && setup.entry_zone_high > 0 ? (
                        `$${setup.entry_zone_low.toFixed(1)} - $${setup.entry_zone_high.toFixed(1)}`
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-slate-100">
                      {setup.preferred_entry > 0 ? `$${setup.preferred_entry.toFixed(2)}` : "—"}
                    </td>
                    <td className="py-3 px-3 text-right text-rose-400">
                      {setup.stop_loss > 0 ? `$${setup.stop_loss.toFixed(2)}` : "—"}
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400">
                      {setup.take_profit > 0 ? `$${setup.take_profit.toFixed(2)}` : "—"}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-300">
                      {setup.reward_to_risk > 0 ? `${setup.reward_to_risk.toFixed(2)}x` : "—"}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {setup.liquidity_sweep_detected ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                      ) : (
                        <XCircle className="w-4 h-4 text-slate-600 inline" />
                      )}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {setup.mss_detected ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                      ) : (
                        <XCircle className="w-4 h-4 text-slate-600 inline" />
                      )}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {setup.eligible_for_signal ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 inline animate-pulse" />
                      ) : (
                        <XCircle className="w-4 h-4 text-slate-500 inline" />
                      )}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-400 text-[11px]">
                      {new Date(setup.evaluated_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
    )}

    {/* DETAIL DRAWER / INSPECT MODAL */}
      {activeSetupId && activeSymbol && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border-l border-slate-700/80 w-full max-w-2xl h-full shadow-2xl p-6 overflow-y-auto font-mono text-xs text-slate-200 space-y-6 relative animate-in slide-in-from-right">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 sticky top-0 bg-slate-900 pt-1 z-10">
              <div>
                <div className="flex items-center gap-2 font-bold text-base text-slate-100">
                  <Sparkles className="w-5 h-5 text-amber-400" />
                  <span>Setup Evaluation Inspector</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  ID: <span className="text-amber-400 font-semibold">{activeSetupId}</span> ({activeSymbol})
                </div>
              </div>
              <button
                onClick={() => {
                  setActiveSetupId(null);
                  setActiveSymbol(null);
                }}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Setup Overview Bar */}
            {activeSetup && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px]">
                <div>
                  <span className="text-slate-400 text-[10px] block">Direction</span>
                  <Badge text={activeSetup.direction} variant="direction" size="sm" />
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">State</span>
                  <Badge text={activeSetup.setup_state} variant="setup_state" size="sm" />
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Pref Entry</span>
                  <span className="font-bold text-slate-100">${activeSetup.preferred_entry}</span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">R:R Ratio</span>
                  <span className="font-bold text-emerald-400">{activeSetup.reward_to_risk}x</span>
                </div>
              </div>
            )}

            {/* Live Evaluation Fetch State */}
            {isLoadingLiveEval ? (
              <div className="p-8 text-center bg-slate-950/40 rounded-lg border border-slate-800 space-y-2">
                <div className="w-6 h-6 border-2 border-slate-700 border-t-amber-400 rounded-full animate-spin mx-auto" />
                <div className="text-slate-400">Evaluating multi-timeframe EMA matrices...</div>
              </div>
            ) : liveEvalError ? (
              <div className="p-4 bg-rose-950/60 border border-rose-500/50 rounded-lg text-rose-300 space-y-1">
                <div className="font-bold flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-rose-400" /> Evaluation Blocked or Unavailable
                </div>
                <div>
                  {(liveEvalError as any)?.message || "409/404: Setup invalidated or blocked by market regime limits."}
                </div>
              </div>
            ) : liveEval ? (
              <div className="space-y-6">
                {/* 1. Trend Summaries (1m, 5m, 15m) */}
                <div className="space-y-2">
                  <h4 className="font-bold text-slate-100 uppercase text-[11px] text-sky-400 flex items-center gap-1.5">
                    <Activity className="w-4 h-4" /> Multi-Timeframe Trend Summaries
                  </h4>
                  <div className="grid grid-cols-3 gap-2">
                    {Object.entries(liveEval.trend_summaries || {}).map(([tfKey, summary]) => (
                      <div key={tfKey} className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-center space-y-1">
                        <span className="text-[10px] text-slate-400 uppercase block font-semibold">{tfKey.replace("_", " ")}</span>
                        <div className="font-bold text-emerald-400 uppercase">{summary.direction}</div>
                        <div className="text-[10px] text-slate-300">Strength: {Math.round(summary.strength * 100)}%</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 2. EMA Snapshot & Entry Zone */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                    <h5 className="font-bold text-amber-400 text-[11px] uppercase">EMA Matrix Snapshot</h5>
                    <div className="space-y-1 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-slate-400">EMA 9:</span>
                        <span className="text-slate-100">${liveEval.ema_snapshot?.ema_9}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">EMA 21:</span>
                        <span className="text-slate-100">${liveEval.ema_snapshot?.ema_21}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">EMA 50:</span>
                        <span className="text-slate-100">${liveEval.ema_snapshot?.ema_50}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">EMA 200:</span>
                        <span className="text-slate-100">${liveEval.ema_snapshot?.ema_200}</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                    <h5 className="font-bold text-emerald-400 text-[11px] uppercase">Entry Zone & Pullback</h5>
                    <div className="space-y-1 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Pullback Depth:</span>
                        <span className="text-emerald-300">{liveEval.pullback_detection?.pullback_depth}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Touch EMA:</span>
                        <span className="text-slate-100">{liveEval.pullback_detection?.touch_ema}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Volume Surge:</span>
                        <span className="text-sky-300">{liveEval.volume?.volume_surge ? "YES" : "NO"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Volume Ratio:</span>
                        <span className="text-slate-100">{liveEval.volume?.volume_ratio}x</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. Rejection & Liquidity Sweep & MSS */}
                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
                  <h5 className="font-bold text-sky-400 text-[11px] uppercase">Structure & Confirmation Flags</h5>
                  <div className="grid grid-cols-2 gap-3 text-[11px]">
                    <div>
                      <span className="text-slate-400 block">Rejection Pattern:</span>
                      <span className="text-slate-100 font-semibold">{liveEval.rejection_confirmation?.pattern_name || "Pinbar Wick"}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Liquidity Sweep:</span>
                      <span className="text-emerald-400 font-semibold">
                        {liveEval.liquidity_sweep?.detected ? `YES (${liveEval.liquidity_sweep.type})` : "NO"}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Market Structure Shift:</span>
                      <span className="text-emerald-400 font-semibold">
                        {liveEval.market_structure_shift?.detected ? `YES (Level: $${liveEval.market_structure_shift.break_level})` : "NO"}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Freshness:</span>
                      <span className="text-slate-300">{liveEval.data_freshness?.age_seconds}s age</span>
                    </div>
                  </div>
                </div>

                {/* 4. Reasons Met & Failed Conditions Lists */}
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <h5 className="font-bold text-emerald-400 text-[11px] uppercase flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Met Setup Criteria
                    </h5>
                    <ul className="space-y-1 text-[11px]">
                      {liveEval.reasons?.map((r, i) => (
                        <li key={i} className="bg-emerald-950/30 border border-emerald-500/30 p-2 rounded text-emerald-300">
                          • {r}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {liveEval.failed_conditions && liveEval.failed_conditions.length > 0 && (
                    <div className="space-y-1.5">
                      <h5 className="font-bold text-rose-400 text-[11px] uppercase flex items-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> Failed Conditions
                      </h5>
                      <ul className="space-y-1 text-[11px]">
                        {liveEval.failed_conditions.map((f, i) => (
                          <li key={i} className="bg-rose-950/30 border border-rose-500/30 p-2 rounded text-rose-300">
                            • {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};
