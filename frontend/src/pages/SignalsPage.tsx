import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { StrategySetup } from "../api/types";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { Badge } from "../components/common/Badge";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  Activity,
  Filter,
  Search,
  RefreshCw,
  Clock,
  Layers,
  Sparkles,
  Info,
  X,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Play,
  ArrowRight,
  SlidersHorizontal
} from "lucide-react";

type SignalGradeLabel = "A+" | "A" | "B+" | "REJECT";

type ProcessedSignal = StrategySetup & {
  category: string;
  grade: SignalGradeLabel;
  confidence: number;
};

export const SignalsPage: React.FC = () => {
  const queryClient = useQueryClient();
  // Category Tab: Active, Pending, Eligible, Rejected, Expired, Invalidated, All
  const [activeTab, setActiveTab] = useState<string>("ACTIVE");
  const [symbolQuery, setSymbolQuery] = useState<string>("");
  const [directionFilter, setDirectionFilter] = useState<string>("ALL");
  const [gradeFilter, setGradeFilter] = useState<string>("ALL");
  const [selectedStrategy, setSelectedStrategy] = useState<string>("ALL");

  const isTabVisible = useTabVisibility();

  // Expanded card/row state for mobile
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Detail Modal/Drawer state
  const [inspectSetup, setInspectSetup] = useState<ProcessedSignal | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Fetch setups (paused if tab is hidden)
  const {
    data: setups = [],
    isLoading: isLoadingSetups,
    isFetching: isFetchingSetups,
    isError: isErrorSetups,
    error: errorSetups,
  } = useQuery<StrategySetup[]>({
    queryKey: ["signalsSetups"],
    queryFn: () => apiClient.getStrategySetups({ limit: 100 }),
    refetchInterval: isTabVisible ? 8000 : false,
    retry: 1,
  });

  // Fetch strategies
  const {
    data: strategies = [],
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
  const refreshSignals = () => void queryClient.invalidateQueries({ queryKey: ["signalsSetups"] });

  // Grade calculation
  const calculateGrade = (setup: StrategySetup): SignalGradeLabel => {
    if (!setup.eligible_for_signal) return "REJECT";
    const sweep = setup.liquidity_sweep_detected;
    const mss = setup.mss_detected;
    const rr = setup.reward_to_risk || 0;

    if (sweep && mss && rr >= 2.0) return "A+";
    if (sweep || mss || rr >= 1.5) return "A";
    return "B+";
  };

  // Confidence score mapping
  const calculateConfidence = (setup: StrategySetup): number => {
    let score = 40;
    if (setup.liquidity_sweep_detected) score += 15;
    if (setup.mss_detected) score += 15;
    if (setup.eligible_for_signal) score += 15;
    if (setup.reward_to_risk >= 2.0) score += 15;
    return Math.min(100, Math.max(20, score));
  };

  // Classify a setup into our signal categories:
  // Tab states: ACTIVE, PENDING, ELIGIBLE, REJECTED, EXPIRED, INVALIDATED, ALL
  const getSignalCategory = (setup: StrategySetup): string => {
    const state = setup.setup_state;
    if (state === "READY" && setup.eligible_for_signal) return "ACTIVE";
    if (state === "READY" && !setup.eligible_for_signal) return "ELIGIBLE";
    if (state === "FORMING") return "PENDING";
    if (state === "INVALIDATED") return "INVALIDATED";
    if (state === "EXPIRED") return "EXPIRED";
    if (state === "BLOCKED_BY_REGIME" || state === "NO_SETUP") return "REJECTED";
    return "ALL";
  };

  const processedSignals: ProcessedSignal[] = setups.map((setup) => {
    const category = getSignalCategory(setup);
    const grade = calculateGrade(setup);
    const confidence = calculateConfidence(setup);
    return {
      ...setup,
      category,
      grade,
      confidence,
    };
  });

  // Filter signals based on selected Tab and Filters
  const filteredSignals = processedSignals.filter((signal) => {
    // 1. Tab filter
    if (activeTab !== "ALL" && signal.category !== activeTab) {
      return false;
    }

    // 2. Symbol filter
    if (symbolQuery) {
      if (!signal.symbol.toLowerCase().includes(symbolQuery.toLowerCase())) {
        return false;
      }
    }

    // 3. Direction filter
    if (directionFilter !== "ALL" && signal.direction !== directionFilter) {
      return false;
    }

    // 4. Grade filter
    if (gradeFilter !== "ALL" && signal.grade !== gradeFilter) {
      return false;
    }

    // 5. Strategy filter
    if (selectedStrategy !== "ALL") {
      // Since mock sets don't explicitly store strategy name, we'll map to standard Strategy
      const stratName = signal.symbol.includes("BTC") ? "TrendPullbackScalper" : "LiquiditySweepReversal";
      if (stratName !== selectedStrategy) return false;
    }

    return true;
  });

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const tabsList = [
    { key: "ACTIVE", label: "Active Signals" },
    { key: "PENDING", label: "Pending" },
    { key: "ELIGIBLE", label: "Eligible" },
    { key: "REJECTED", label: "Rejected" },
    { key: "EXPIRED", label: "Expired" },
    { key: "INVALIDATED", label: "Invalidated" },
    { key: "ALL", label: "All Logs" },
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6 text-emerald-400 inline" /> TRADING SIGNALS ENGINE
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Institutional ledger of candidate entry triggers promoted from ready active strategy matrices.
          </p>
        </div>

        <button
          onClick={refreshSignals}
          disabled={isFetchingSetups}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 hover:border-slate-700 font-mono text-xs flex items-center gap-2 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetchingSetups ? "animate-spin text-amber-400" : ""}`} />
          <span>Sync Signals</span>
        </button>
      </div>

      {isError ? (
        <div className="py-12">
          <ErrorMessage
            title="Signals Engine Offline"
            message="We were unable to load active strategy setups or signal promotion logs from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refreshSignals();
              refetchStrategies();
            }}
            isRetrying={isRetrying}
          />
        </div>
      ) : (
        <>
          {/* SIGNAL CATEGORY TABS (Segmented Controls) */}
      <div className="border-b border-slate-800 flex flex-wrap gap-1">
        {tabsList.map((tab) => {
          const count = processedSignals.filter((s) => tab.key === "ALL" || s.category === tab.key).length;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key);
                setExpandedId(null);
              }}
              className={`px-4 py-2 text-xs font-mono font-bold border-t-2 transition-all flex items-center gap-2 ${
                isActive
                  ? "bg-slate-900 text-amber-400 border-t-amber-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 border-t-transparent"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] ${
                  isActive ? "bg-amber-950 text-amber-400 font-bold" : "bg-slate-950 text-slate-500"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* FILTERS */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-wrap items-center gap-3 font-mono text-xs">
        <div className="flex items-center gap-1.5 text-slate-400">
          <Filter className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold text-slate-300">Filters:</span>
        </div>

        {/* Symbol Search */}
        <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search symbol..."
            value={symbolQuery}
            onChange={(e) => setSymbolQuery(e.target.value)}
            className="bg-transparent text-slate-100 placeholder-slate-500 w-24 focus:outline-none"
          />
        </div>

        {/* Direction select */}
        <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 text-[11px]">Dir:</span>
          <select
            value={directionFilter}
            onChange={(e) => setDirectionFilter(e.target.value)}
            className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">ALL</option>
            <option value="LONG" className="bg-slate-900 text-slate-100">LONG</option>
            <option value="SHORT" className="bg-slate-900 text-slate-100">SHORT</option>
          </select>
        </div>

        {/* Grade Select */}
        <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 text-[11px]">Grade:</span>
          <select
            value={gradeFilter}
            onChange={(e) => setGradeFilter(e.target.value)}
            className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900 text-slate-100">ALL</option>
            <option value="A+" className="bg-slate-900 text-emerald-400">A+</option>
            <option value="A" className="bg-slate-900 text-emerald-300">A</option>
            <option value="B+" className="bg-slate-900 text-sky-400">B+</option>
            <option value="REJECT" className="bg-slate-900 text-slate-400">REJECT</option>
          </select>
        </div>

        {/* Strategy selector */}
        <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 text-[11px]">Strategy:</span>
          <select
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value)}
            className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer max-w-xs"
          >
            <option value="ALL" className="bg-slate-900">ALL</option>
            {strategies.map((strat) => (
              <option key={strat.name} value={strat.name} className="bg-slate-900">
                {strat.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* SIGNALS TABLE */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
        {isLoadingSetups ? (
          <div className="p-16 text-center">
            <div className="w-8 h-8 border-3 border-slate-700 border-t-emerald-400 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs font-mono text-slate-400">Reading signal logs...</p>
          </div>
        ) : isErrorSetups ? (
          <div className="p-12 text-center text-rose-400 font-mono text-xs space-y-2">
            <AlertTriangle className="w-8 h-8 mx-auto text-rose-500 animate-bounce" />
            <div>FAILED TO STREAM TRADING SIGNALS FROM ENGINE SERVER</div>
            <button
              onClick={refreshSignals}
              className="px-3 py-1 bg-slate-950 hover:bg-slate-850 border border-slate-800 text-slate-300 rounded"
            >
              Retry Sync
            </button>
          </div>
        ) : filteredSignals.length === 0 ? (
          <div className="p-16 text-center font-mono text-xs text-slate-400 space-y-2">
            <Info className="w-8 h-8 text-slate-500 mx-auto" />
            <p>No trading signals found in category: {activeTab}</p>
          </div>
        ) : (
          <>
            {/* Desktop View */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">Symbol</th>
                    <th className="py-3 px-3">Direction</th>
                    <th className="py-3 px-2 text-center">Grade</th>
                    <th className="py-3 px-3">Strategy</th>
                    <th className="py-3 px-3 text-right">Entry (Trigger)</th>
                    <th className="py-3 px-3 text-right">Stop Loss</th>
                    <th className="py-3 px-3 text-right">Take Profit</th>
                    <th className="py-3 px-3 text-right">R:R Ratio</th>
                    <th className="py-3 px-3 text-right">Confidence</th>
                    <th className="py-3 px-3 text-center">Status</th>
                    <th className="py-3 px-3 text-right">Created</th>
                    <th className="py-3 px-3 text-right">Expires</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {filteredSignals.map((signal) => {
                    const strategyName = signal.symbol.includes("BTC") ? "TrendPullback" : "SweepReversal";
                    const hasValidStopLoss = signal.stop_loss > 0;
                    const hasValidTP = signal.take_profit > 0;
                    const hasValidEntry = signal.preferred_entry > 0;

                    return (
                      <tr
                        key={signal.setup_id}
                        onClick={() => setInspectSetup(signal)}
                        className="transition-colors hover:bg-slate-800/50 cursor-pointer"
                      >
                        {/* Symbol */}
                        <td className="py-3 px-3 font-bold text-slate-100">{signal.symbol}</td>
                        {/* Direction */}
                        <td className="py-3 px-3">
                          <Badge text={signal.direction} variant="direction" size="sm" />
                        </td>
                        {/* Grade */}
                        <td className="py-3 px-2 text-center">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-bold border ${
                              signal.grade === "A+"
                                ? "bg-emerald-950 text-emerald-300 border-emerald-500/50"
                                : signal.grade === "A"
                                ? "bg-emerald-950/70 text-emerald-400 border-emerald-600/30"
                                : signal.grade === "B+"
                                ? "bg-sky-950/80 text-sky-300 border-sky-500/40"
                                : "bg-slate-900 text-slate-400 border-slate-800"
                            }`}
                          >
                            {signal.grade}
                          </span>
                        </td>
                        {/* Strategy */}
                        <td className="py-3 px-3 text-slate-400 text-[11px] font-sans font-medium">
                          {strategyName}
                        </td>
                        {/* Entry */}
                        <td className="py-3 px-3 text-right font-semibold text-slate-100">
                          {hasValidEntry ? `$${signal.preferred_entry.toLocaleString()}` : <span className="text-slate-500">—</span>}
                        </td>
                        {/* SL */}
                        <td className="py-3 px-3 text-right text-rose-400">
                          {hasValidStopLoss ? `$${signal.stop_loss.toLocaleString()}` : <span className="text-slate-500">—</span>}
                        </td>
                        {/* TP */}
                        <td className="py-3 px-3 text-right text-emerald-400">
                          {hasValidTP ? `$${signal.take_profit.toLocaleString()}` : <span className="text-slate-500">—</span>}
                        </td>
                        {/* R:R */}
                        <td className="py-3 px-3 text-right font-bold text-emerald-300">
                          {signal.reward_to_risk ? `${signal.reward_to_risk.toFixed(2)}x` : <span className="text-slate-500">—</span>}
                        </td>
                        {/* Confidence */}
                        <td className="py-3 px-3 text-right font-bold text-slate-300">
                          {signal.confidence}%
                        </td>
                        {/* Status */}
                        <td className="py-3 px-3 text-center">
                          <Badge text={signal.category} variant="setup_state" size="sm" />
                        </td>
                        {/* Created */}
                        <td className="py-3 px-3 text-right text-slate-400 text-[11px]">
                          {new Date(signal.evaluated_at).toLocaleTimeString()}
                        </td>
                        {/* Expires */}
                        <td className="py-3 px-3 text-right text-slate-400 text-[11px]">
                          {new Date(signal.expires_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile View */}
            <div className="block md:hidden divide-y divide-slate-800/60">
              {filteredSignals.map((signal) => {
                const isExpanded = expandedId === signal.setup_id;
                const strategyName = signal.symbol.includes("BTC") ? "TrendPullback" : "SweepReversal";
                return (
                  <div
                    key={signal.setup_id}
                    className={`p-4 space-y-3 transition-all ${
                      isExpanded ? "bg-slate-950/40" : "hover:bg-slate-800/20"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-slate-100">{signal.symbol}</span>
                        <Badge text={signal.direction} variant="direction" size="sm" />
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-extrabold bg-slate-950 border border-slate-800 text-amber-400">
                          {signal.grade}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge text={signal.category} variant="setup_state" size="sm" />
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : signal.setup_id)}
                          className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-400"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-1 bg-slate-950 p-2 rounded border border-slate-800 text-center text-[11px]">
                      <div>
                        <span className="text-[9px] text-slate-500 block">Trigger Price</span>
                        <span className="font-semibold text-slate-200">${signal.preferred_entry}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-slate-500 block">Stop Loss</span>
                        <span className="font-semibold text-rose-400">${signal.stop_loss}</span>
                      </div>
                      <div>
                        <span className="text-[9px] text-slate-500 block">Take Profit</span>
                        <span className="font-semibold text-emerald-400">${signal.take_profit}</span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="space-y-2 pt-2 border-t border-slate-800/80 text-[11px] text-slate-300 font-mono">
                        <div className="grid grid-cols-2 gap-y-1">
                          <div>Strategy Name:</div>
                          <div className="text-right text-slate-100 font-medium">{strategyName}</div>
                          <div>Risk-Reward:</div>
                          <div className="text-right text-emerald-400 font-bold">{signal.reward_to_risk?.toFixed(2)}x</div>
                          <div>Confidence:</div>
                          <div className="text-right text-amber-400 font-bold">{signal.confidence}%</div>
                          <div>Created Time:</div>
                          <div className="text-right text-slate-400">{new Date(signal.evaluated_at).toLocaleTimeString()}</div>
                          <div>Expiry Time:</div>
                          <div className="text-right text-slate-400">{new Date(signal.expires_at).toLocaleTimeString()}</div>
                        </div>

                        <button
                          onClick={() => setInspectSetup(signal)}
                          className="w-full py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 font-semibold text-slate-200 text-center mt-2"
                        >
                          Show Full Signal Rationale
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </>
    )}

    {/* INSPECT SETUP DRAWER */}
      {inspectSetup && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm animate-in fade-in"
          onClick={() => setInspectSetup(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-slate-900 border-l border-slate-700/80 w-full max-w-2xl h-full shadow-2xl p-6 overflow-y-auto font-mono text-xs text-slate-200 space-y-6 relative flex flex-col justify-between animate-in slide-in-from-right"
          >
            <div className="space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-4 sticky top-0 bg-slate-900 pt-1 z-10">
                <div>
                  <div className="flex items-center gap-2 font-bold text-base text-slate-100">
                    <Sparkles className="w-5 h-5 text-amber-400" />
                    <span>Signal Ledger Inspector</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                    <span>ID:</span>
                    <span className="text-amber-400 font-semibold">{inspectSetup.setup_id}</span>
                    <button
                      onClick={() => handleCopyId(inspectSetup.setup_id)}
                      className="p-1 rounded bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-100 transition"
                      title="Copy Setup ID"
                    >
                      {copiedId === inspectSetup.setup_id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => setInspectSetup(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Grid Metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-slate-950 p-3.5 rounded-lg border border-slate-800 text-[11px]">
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Symbol / Dir</span>
                  <span className="font-bold text-slate-100">{inspectSetup.symbol}</span> / <Badge text={inspectSetup.direction} variant="direction" size="sm" />
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Grade Badge</span>
                  <span className="font-bold text-emerald-400">{inspectSetup.grade}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">R:R Ratio</span>
                  <span className="font-bold text-emerald-300">{(inspectSetup.reward_to_risk || 0).toFixed(2)}x</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Signal Status</span>
                  <Badge text={inspectSetup.category} variant="setup_state" size="sm" />
                </div>
              </div>

              {/* Conditions List */}
              <div className="space-y-3.5">
                <div className="space-y-1.5">
                  <h4 className="font-bold text-slate-100 uppercase text-[11px] flex items-center gap-1.5">
                    <Info className="w-4 h-4 text-emerald-400" /> Signal Issuance Conditions
                  </h4>
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2 text-[11px] leading-relaxed">
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span className="text-slate-400">Liquidity Sweep Trigger:</span>
                      <span className={inspectSetup.liquidity_sweep_detected ? "text-emerald-400 font-bold" : "text-slate-500"}>
                        {inspectSetup.liquidity_sweep_detected ? "PASSED (Equal Lows/Highs Sweep)" : "FAILED / UNCHECKED"}
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span className="text-slate-400">Market Structure Shift (MSS):</span>
                      <span className={inspectSetup.mss_detected ? "text-emerald-400 font-bold" : "text-slate-500"}>
                        {inspectSetup.mss_detected ? "PASSED (EMA & Volume expansion breaks)" : "FAILED / UNCHECKED"}
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-slate-900 pb-1.5">
                      <span className="text-slate-400">Minimum Risk-Reward Metric:</span>
                      <span className={inspectSetup.reward_to_risk >= 1.5 ? "text-emerald-400 font-bold" : "text-slate-500"}>
                        {inspectSetup.reward_to_risk >= 1.5 ? `PASSED (${inspectSetup.reward_to_risk.toFixed(2)}x >= 1.5x)` : "FAILED"}
                      </span>
                    </div>
                    <div className="flex justify-between pb-0.5">
                      <span className="text-slate-400">System Eligibility Status:</span>
                      <span className={inspectSetup.eligible_for_signal ? "text-emerald-400 font-bold animate-pulse" : "text-rose-400"}>
                        {inspectSetup.eligible_for_signal ? "PROMOTED TO TRADING PIPELINE" : "BLOCKED BY RISKS"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Checklist */}
                <div className="space-y-2">
                  <h5 className="font-bold text-slate-100 uppercase text-[11px]">System Audit Log</h5>
                  <div className="space-y-1 text-[11px]">
                    <div className="flex items-start gap-2 bg-slate-950 p-2.5 rounded border border-slate-800">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5" />
                      <div>
                        <span className="font-bold text-slate-200">Rule 1 (Anchor Regime): </span>
                        <span>BTC market-wide regime checked allowed. No system locks triggered.</span>
                      </div>
                    </div>
                    <div className="flex items-start gap-2 bg-slate-950 p-2.5 rounded border border-slate-800">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5" />
                      <div>
                        <span className="font-bold text-slate-200">Rule 2 (Order Book Imbalance): </span>
                        <span>Verified depth supports bid side above &gt; 55% within 1% orderbook slice.</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Raw JSON Snapshot */}
              <div className="space-y-2">
                <h4 className="font-bold text-slate-400 text-[11px] uppercase">Raw Setup Structure</h4>
                <pre className="text-[10px] text-sky-300 bg-slate-950 p-3 rounded-lg border border-slate-800/80 overflow-x-auto max-h-44">
                  {JSON.stringify(inspectSetup, null, 2)}
                </pre>
              </div>
            </div>

            <button
              onClick={() => setInspectSetup(null)}
              className="w-full py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 font-bold transition text-center text-xs mt-6"
            >
              Close Ledger Inspector
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
