import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useSymbol } from "../context/SymbolContext";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { Badge } from "../components/common/Badge";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Zap,
  Info,
  Clock,
  Coins,
} from "lucide-react";

export const RegimePage: React.FC = () => {
  const { selectedSymbol, setSelectedSymbol, symbols } = useSymbol();
  const [snapshotExpanded, setSnapshotExpanded] = useState<boolean>(true);
  const isTabVisible = useTabVisibility();

  // Poll current symbol regime every 15s (paused if tab is hidden)
  const {
    data: symbolRegime,
    isLoading: isLoadingSymbolRegime,
    isError: isErrorSymbolRegime,
    error: symbolRegimeError,
    refetch: refetchSymbolRegime,
    isFetching: isFetchingSymbolRegime,
  } = useQuery({
    queryKey: ["symbolRegime", selectedSymbol],
    queryFn: () => apiClient.getSymbolRegime(selectedSymbol),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  // Poll BTC anchor regime every 15s (paused if tab is hidden)
  const {
    data: btcRegime,
    isLoading: isLoadingBtcRegime,
    isError: isErrorBtcRegime,
    error: btcRegimeError,
    refetch: refetchBtcRegime,
  } = useQuery({
    queryKey: ["btcRegime"],
    queryFn: () => apiClient.getMarketRegimeBtc(),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  const isError = isErrorSymbolRegime || isErrorBtcRegime;
  const anyError = symbolRegimeError || btcRegimeError;
  const isRetrying = isFetchingSymbolRegime;

  const renderNestedValue = (val: any): React.ReactNode => {
    if (val === null || val === undefined) return <span className="text-slate-500">null</span>;
    if (typeof val === "boolean") return <span className="text-amber-400 font-bold">{val ? "TRUE" : "FALSE"}</span>;
    if (typeof val === "number") return <span className="text-emerald-400 font-semibold">{val.toLocaleString(undefined, { maximumFractionDigits: 6 })}</span>;
    if (typeof val === "object") {
      return (
        <pre className="text-[11px] font-mono text-sky-300 bg-slate-950 p-2 rounded border border-slate-800 overflow-x-auto">
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    return <span className="text-slate-200">{String(val)}</span>;
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header & Symbol Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-amber-400 inline" /> MARKET REGIME ANALYSIS
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Volatilities, EMA trends, liquidity depth, and safety conditions for trade entry permission.
          </p>
        </div>

        {/* Symbol Quick Switcher */}
        <div className="flex items-center gap-2 bg-slate-900 p-2 rounded-xl border border-slate-800">
          <Coins className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-mono text-slate-400">Inspecting:</span>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-slate-950 text-amber-400 font-mono text-xs font-bold px-2 py-1 rounded border border-slate-700 cursor-pointer"
          >
            {symbols.map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.symbol}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isError ? (
        <div className="py-12">
          <ErrorMessage
            title="Market Regime Data Unavailable"
            message="We were unable to load the regime data for the selected symbol and BTC anchor from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refetchSymbolRegime();
              refetchBtcRegime();
            }}
            isRetrying={isRetrying}
          />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* BTC Anchor Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2 font-mono font-bold text-slate-100 text-sm">
              <Zap className="w-4 h-4 text-amber-400" /> BTC MARKET ANCHOR
            </div>
            <Badge text="ANCHOR SYMBOL" variant="default" size="sm" />
          </div>

          {isLoadingBtcRegime ? (
            <div className="h-24 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-slate-700 border-t-amber-400 rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400 text-[10px] block mb-1 uppercase">Primary Regime</span>
                  <Badge text={btcRegime?.primary_regime || "TRENDING_BULLISH"} variant="regime" size="md" />
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block mb-1 uppercase">Entry Permission</span>
                  <Badge text={btcRegime?.entry_permission || "ALLOW_LONG"} variant="permission" size="md" />
                </div>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Confidence: <strong className="text-emerald-400">{Math.round((btcRegime?.confidence_score || 0) * 100)}%</strong></span>
                <span>Trend Direction: <strong className="text-sky-300 uppercase">{btcRegime?.trend_direction || "bullish"}</strong></span>
              </div>
            </div>
          )}
        </div>

        {/* Selected Symbol Regime Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2 font-mono font-bold text-slate-100 text-sm">
              <Coins className="w-4 h-4 text-emerald-400" /> {selectedSymbol} TARGET REGIME
            </div>
            {symbolRegime && <Badge text={symbolRegime.data_fresh ? "FRESH DATA" : "STALE DATA"} variant="default" size="sm" />}
          </div>

          {isLoadingSymbolRegime ? (
            <div className="h-24 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
            </div>
          ) : symbolRegimeError ? (
            <div className="p-4 bg-rose-950/60 border border-rose-500/50 rounded-lg text-rose-300 text-xs font-mono space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-rose-400" /> Regime Unavailable for {selectedSymbol}
              </div>
              <div>
                {(symbolRegimeError as any)?.message || "404/422: Insufficient historical candles to compute indicators."}
              </div>
            </div>
          ) : symbolRegime ? (
            <div className="space-y-3 font-mono text-xs">
              <div className="grid grid-cols-2 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-400 text-[10px] block mb-1 uppercase">Primary Regime</span>
                  <Badge text={symbolRegime.primary_regime} variant="regime" size="md" />
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block mb-1 uppercase">Entry Permission</span>
                  <Badge text={symbolRegime.entry_permission} variant="permission" size="md" />
                </div>
              </div>
              <div className="flex items-center justify-between text-slate-300">
                <span>Confidence: <strong className="text-amber-400">{Math.round((symbolRegime.confidence_score || 0) * 100)}%</strong></span>
                <span>Spread: <strong className="text-slate-100">{symbolRegime.spread_value ? `${symbolRegime.spread_value} bps` : "N/A"}</strong></span>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Market-wide Block Banner if True */}
      {symbolRegime?.market_wide_block && (
        <div className="p-4 bg-rose-950/80 border border-rose-500 rounded-xl text-rose-200 text-xs font-mono font-bold flex items-center gap-3 animate-pulse shadow-lg shadow-rose-950/80">
          <AlertTriangle className="w-6 h-6 text-rose-400 shrink-0" />
          <div>
            <div>MARKET WIDE ENTRY BLOCK IS CURRENTLY ACTIVE</div>
            <div className="text-[11px] font-normal text-rose-300 mt-0.5">
              High volatility or abnormal spread detected on BTC anchor. All order generator pipelines are strictly blocked.
            </div>
          </div>
        </div>
      )}

      {/* Detailed Evaluation Lists: Reasons & Safety Conditions */}
      {symbolRegime && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Reasons List */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
              <Info className="w-4 h-4 text-sky-400" /> Evaluation Rationale
            </h3>
            {symbolRegime.reasons && symbolRegime.reasons.length > 0 ? (
              <ul className="space-y-2 font-mono text-xs text-slate-300">
                {symbolRegime.reasons.map((reason, idx) => (
                  <li key={idx} className="flex items-start gap-2 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs font-mono text-slate-500">No rationale statements generated.</p>
            )}
          </div>

          {/* Safety Conditions List */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Safety Conditions Checklist
            </h3>
            {symbolRegime.safety_conditions && symbolRegime.safety_conditions.length > 0 ? (
              <ul className="space-y-2 font-mono text-xs text-slate-300">
                {symbolRegime.safety_conditions.map((cond, idx) => (
                  <li key={idx} className="flex items-start gap-2 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                    <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{cond}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs font-mono text-slate-500">No safety check logs attached.</p>
            )}
          </div>
        </div>
      )}

      {/* Collapsible Indicator Snapshot Table */}
      {symbolRegime?.indicator_snapshot && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
          <button
            onClick={() => setSnapshotExpanded(!snapshotExpanded)}
            className="w-full p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between text-xs font-mono font-bold text-slate-200 hover:bg-slate-800/60 transition"
          >
            <span className="flex items-center gap-2">
              {snapshotExpanded ? <ChevronDown className="w-4 h-4 text-amber-400" /> : <ChevronRight className="w-4 h-4 text-amber-400" />}
              INDICATOR SNAPSHOT & TECHNICAL COEFFICIENTS ({Object.keys(symbolRegime.indicator_snapshot).length} metrics)
            </span>
            <span className="text-slate-400 font-normal text-[11px]">
              Evaluated at: {new Date(symbolRegime.evaluated_at).toLocaleTimeString()}
            </span>
          </button>

          {snapshotExpanded && (
            <div className="p-4 overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider bg-slate-950/60">
                    <th className="py-2.5 px-3">Indicator Metric</th>
                    <th className="py-2.5 px-3">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {Object.entries(symbolRegime.indicator_snapshot).map(([key, val]) => (
                    <tr key={key} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-3 font-semibold text-slate-300 font-mono">{key}</td>
                      <td className="py-2.5 px-3">{renderNestedValue(val)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
        </>
      )}
    </div>
  );
};
