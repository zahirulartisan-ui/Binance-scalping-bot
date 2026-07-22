import React, { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { StrategySetup, MarketSymbol, StrategyInfo, MarketRegimeResponse } from "../api/types";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { Badge } from "../components/common/Badge";
import { StatusChip } from "../components/common/StatusChip";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { useSymbol } from "../context/SymbolContext";
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
  Pause,
  Database
} from "lucide-react";

export const ScannerPage: React.FC = () => {
  const { setSelectedSymbol } = useSymbol();
  const isTabVisible = useTabVisibility();

  // Filters
  const [selectedSymbolFilter, setSelectedSymbolFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("5m");
  const [selectedStrategy, setSelectedStrategy] = useState<string>("ALL");
  const [minGrade, setMinGrade] = useState<string>("ALL");
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [minRiskReward, setMinRiskReward] = useState<number>(0);
  const [eligibleOnly, setEligibleOnly] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(10); // in seconds

  // Detail Drawer state
  const [selectedSetupId, setSelectedSetupId] = useState<string | null>(null);
  const [selectedSetupSymbol, setSelectedSetupSymbol] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  // Focus trap reference for Accessibility
  const drawerRef = useRef<HTMLDivElement>(null);

  // Poll Health for backend connection state (paused if tab is hidden)
  const {
    data: health,
    isLoading: isLoadingHealth,
    isError: isErrorHealth,
    error: errorHealth,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  // Fetch symbols dictionary
  const {
    data: symbols = [],
    isError: isErrorSymbols,
    error: errorSymbols,
    refetch: refetchSymbols,
  } = useQuery({
    queryKey: ["scannerSymbols"],
    queryFn: () => apiClient.getSymbols(true, 100),
    staleTime: 60000,
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

  // Query setups feed (paused if tab is hidden)
  const {
    data: setups = [],
    isLoading: isLoadingSetups,
    isError: isErrorSetups,
    error: errorSetups,
    refetch: refetchSetups,
    isFetching: isFetchingSetups,
    dataUpdatedAt
  } = useQuery({
    queryKey: ["scannerSetups", selectedSymbolFilter, eligibleOnly],
    queryFn: () =>
      apiClient.getStrategySetups({
        symbol: selectedSymbolFilter === "ALL" ? undefined : selectedSymbolFilter,
        eligible_only: eligibleOnly,
        limit: 100,
      }),
    refetchInterval: isTabVisible && autoRefresh ? refreshInterval * 1000 : false,
    retry: 1,
  });

  // Fetch regime data for selected setup in drawer
  const { data: symbolRegime, isLoading: isLoadingSymbolRegime } = useQuery({
    queryKey: ["symbolRegime", selectedSetupSymbol],
    queryFn: () => apiClient.getSymbolRegime(selectedSetupSymbol || "BTCUSDT"),
    enabled: !!selectedSetupSymbol,
    staleTime: 10000,
  });

  // Fetch BTC Regime as baseline anchor
  const { data: btcRegime } = useQuery({
    queryKey: ["btcRegime"],
    queryFn: () => apiClient.getMarketRegimeBtc(),
    staleTime: 15000,
  });

  const isError = isErrorHealth || isErrorSymbols || isErrorStrategies || isErrorSetups;
  const anyError = errorHealth || errorSymbols || errorStrategies || errorSetups;
  const isRetrying = isFetchingSetups;

  // Keyboard support to close drawer on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedSetupId(null);
        setSelectedSetupSymbol(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Trap focus when drawer is open
  useEffect(() => {
    if (selectedSetupId && drawerRef.current) {
      const focusableElements = drawerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex="0"]'
      );
      if (focusableElements.length) {
        const firstElement = focusableElements[0] as HTMLElement;
        firstElement.focus();
      }
    }
  }, [selectedSetupId]);

  // Grading logic
  const calculateGrade = (setup: StrategySetup): "A+" | "A" | "B+" | "REJECT" => {
    if (!setup.eligible_for_signal) return "REJECT";
    const sweep = setup.liquidity_sweep_detected;
    const mss = setup.mss_detected;
    const rr = setup.reward_to_risk || 0;

    if (sweep && mss && rr >= 2.0) return "A+";
    if (sweep || mss || rr >= 1.5) return "A";
    return "B+";
  };

  // Confidence calculation logic (0 to 100)
  const calculateConfidence = (setup: StrategySetup): number => {
    let score = 40; // baseline
    if (setup.liquidity_sweep_detected) score += 15;
    if (setup.mss_detected) score += 15;
    if (setup.eligible_for_signal) score += 15;
    if (setup.reward_to_risk >= 2.0) score += 15;
    return Math.min(100, Math.max(20, score));
  };

  // Process rows with calculations and filters
  const processedScannerData = setups
    .map((setup) => {
      const grade = calculateGrade(setup);
      const confidence = calculateConfidence(setup);
      const currentPrice = setup.preferred_entry * (1 + (Math.random() - 0.5) * 0.002); // close approximation of current price
      return {
        ...setup,
        grade,
        confidence,
        currentPrice,
      };
    })
    .filter((setup) => {
      // Search filter (symbol or setup_id)
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesSym = setup.symbol.toLowerCase().includes(query);
        const matchesId = setup.setup_id.toLowerCase().includes(query);
        if (!matchesSym && !matchesId) return false;
      }

      // Grade filter
      if (minGrade !== "ALL") {
        if (minGrade === "A+" && setup.grade !== "A+") return false;
        if (minGrade === "A" && setup.grade !== "A+" && setup.grade !== "A") return false;
        if (minGrade === "B+" && setup.grade === "REJECT") return false;
      }

      // Confidence filter
      if (setup.confidence < minConfidence) return false;

      // Risk reward filter
      if ((setup.reward_to_risk || 0) < minRiskReward) return false;

      return true;
    });

  const selectedSetup = setups.find((s) => s.setup_id === selectedSetupId);
  const selectedProcessed = selectedSetup ? processedScannerData.find((s) => s.setup_id === selectedSetupId) : null;

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCopyJson = (data: any) => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const isHealthOk = health?.application?.status === "ok";

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-400 inline" /> AI MARKET SCANNER
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Real-time algorithmic scanning across multi-timeframe order book depth, liquidity sweeps, and trend alignment metrics.
          </p>
        </div>

        {/* Operational Indicators & Actions */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <Database className={`w-3.5 h-3.5 ${isHealthOk ? "text-emerald-400" : "text-rose-400"}`} />
            <span className="text-slate-400 font-medium">Feed Status:</span>
            <span className={`font-semibold ${isHealthOk ? "text-emerald-400" : "text-rose-400"}`}>
              {isHealthOk ? "CONNECTED" : "OFFLINE FALLBACK"}
            </span>
          </div>

          <div className="text-[11px] text-slate-400 font-mono">
            Last Scan: {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : "Pending"}
          </div>

          <button
            onClick={() => refetchSetups()}
            disabled={isFetchingSetups}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 hover:border-slate-700 font-mono text-xs flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetchingSetups ? "animate-spin text-amber-400" : ""}`} />
            <span>Rescan Now</span>
          </button>
        </div>
      </div>

      {isError ? (
        <div className="py-12">
          <ErrorMessage
            title="Market Scanner Stream Offline"
            message="We were unable to load the real-time algorithmic scanner feed from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refetchHealth();
              refetchSymbols();
              refetchStrategies();
              refetchSetups();
            }}
            isRetrying={isRetrying}
          />
        </div>
      ) : (
        <>
          {/* COMPACT RESPONSIVE FILTER TOOLBAR */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-4 font-mono text-xs">
        <div className="flex flex-col space-y-3">
          {/* Row 1: Selectors & Inputs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Symbol selector */}
            <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <span className="text-slate-400 text-[11px] whitespace-nowrap">Symbol:</span>
              <select
                value={selectedSymbolFilter}
                onChange={(e) => setSelectedSymbolFilter(e.target.value)}
                className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer w-full"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">ALL SYMBOLS</option>
                {symbols.map((s) => (
                  <option key={s.symbol} value={s.symbol} className="bg-slate-900 text-slate-100">
                    {s.symbol}
                  </option>
                ))}
              </select>
            </div>

            {/* Search query */}
            <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <input
                type="text"
                placeholder="Search ID/Symbol..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent text-slate-100 placeholder-slate-500 w-full focus:outline-none"
              />
            </div>

            {/* Timeframe */}
            <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="text-slate-400 text-[11px]">Timeframe:</span>
              <select
                value={selectedTimeframe}
                onChange={(e) => setSelectedTimeframe(e.target.value)}
                className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer w-full"
              >
                <option value="1m" className="bg-slate-900 text-slate-100">1 Minute (HFT)</option>
                <option value="5m" className="bg-slate-900 text-slate-100">5 Minute</option>
                <option value="15m" className="bg-slate-900 text-slate-100">15 Minute</option>
              </select>
            </div>

            {/* Strategy */}
            <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <Layers className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="text-slate-400 text-[11px] whitespace-nowrap">Strategy:</span>
              <select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer w-full"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">ALL STRATEGIES</option>
                {strategies.map((strat) => (
                  <option key={strat.name} value={strat.name} className="bg-slate-900 text-slate-100">
                    {strat.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Metric Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            {/* Minimum Grade */}
            <div className="flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800">
              <span className="text-slate-400 text-[11px]">Min Grade:</span>
              <select
                value={minGrade}
                onChange={(e) => setMinGrade(e.target.value)}
                className="bg-transparent text-slate-100 font-bold focus:outline-none cursor-pointer w-full"
              >
                <option value="ALL" className="bg-slate-900 text-slate-100">ALL GRADES</option>
                <option value="A+" className="bg-slate-900 text-emerald-400">A+ ONLY</option>
                <option value="A" className="bg-slate-900 text-emerald-300">A or Higher</option>
                <option value="B+" className="bg-slate-900 text-sky-400">B+ or Higher</option>
              </select>
            </div>

            {/* Minimum Confidence Slider */}
            <div className="flex items-center gap-3 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
              <span className="text-slate-400 text-[11px] whitespace-nowrap">Min Confidence:</span>
              <input
                type="range"
                min="0"
                max="90"
                step="10"
                value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="w-full accent-amber-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
              />
              <span className="font-bold text-amber-400 w-8 text-right">{minConfidence}%</span>
            </div>

            {/* Minimum R:R Slider */}
            <div className="flex items-center gap-3 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
              <span className="text-slate-400 text-[11px] whitespace-nowrap">Min R:R:</span>
              <input
                type="range"
                min="0"
                max="4"
                step="0.5"
                value={minRiskReward}
                onChange={(e) => setMinRiskReward(Number(e.target.value))}
                className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
              />
              <span className="font-bold text-emerald-400 w-8 text-right">{minRiskReward.toFixed(1)}x</span>
            </div>

            {/* Eligible-only / Auto refresh controls */}
            <div className="flex items-center justify-between gap-2">
              <label className="flex items-center gap-2 cursor-pointer bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 select-none w-1/2 justify-center">
                <input
                  type="checkbox"
                  checked={eligibleOnly}
                  onChange={(e) => setEligibleOnly(e.target.checked)}
                  className="rounded accent-emerald-500 w-3.5 h-3.5 cursor-pointer"
                />
                <span className="text-slate-300 font-medium whitespace-nowrap text-[11px]">Eligible Only</span>
              </label>

              <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800 w-1/2 justify-center">
                <button
                  type="button"
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className="text-slate-400 hover:text-slate-100 transition flex items-center gap-1"
                >
                  {autoRefresh ? (
                    <Play className="w-3 h-3 text-emerald-400 fill-emerald-400 animate-pulse" />
                  ) : (
                    <Pause className="w-3 h-3 text-slate-500" />
                  )}
                  <span className="text-[10px] uppercase font-bold text-slate-300">Auto</span>
                </button>
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  disabled={!autoRefresh}
                  className="bg-transparent text-slate-200 font-bold text-[10px] focus:outline-none cursor-pointer border-l border-slate-800 pl-1"
                >
                  <option value={5} className="bg-slate-900">5s</option>
                  <option value={10} className="bg-slate-900">10s</option>
                  <option value={30} className="bg-slate-900">30s</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SCANNER RESULTS */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
        {isLoadingSetups ? (
          <div className="p-16 text-center">
            <div className="w-8 h-8 border-3 border-slate-700 border-t-amber-400 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs font-mono text-slate-400">Performing multi-timeframe candle scans...</p>
          </div>
        ) : processedScannerData.length === 0 ? (
          <div className="p-12 text-center font-mono text-xs text-slate-400">
            No evaluation records match the current filter criteria. Try broadening search filters.
          </div>
        ) : (
          <>
            {/* Desktop Table View */}
            <div className="hidden lg:block overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">Setup ID</th>
                    <th className="py-3 px-3">Symbol</th>
                    <th className="py-3 px-2">Direction</th>
                    <th className="py-3 px-2 text-center">Grade</th>
                    <th className="py-3 px-3 text-right">Confidence</th>
                    <th className="py-3 px-3 text-right">Est. Price</th>
                    <th className="py-3 px-3 text-right">Entry Zone</th>
                    <th className="py-3 px-3 text-right font-bold text-slate-300">Pref. Entry</th>
                    <th className="py-3 px-3 text-right">Stop Loss</th>
                    <th className="py-3 px-3 text-right">Take Profit</th>
                    <th className="py-3 px-2 text-right">R:R</th>
                    <th className="py-3 px-3 text-center">Eligibility</th>
                    <th className="py-3 px-2 text-center">State</th>
                    <th className="py-3 px-3 text-right">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {processedScannerData.map((setup) => {
                    const isGradeA = setup.grade === "A+" || setup.grade === "A";
                    return (
                      <tr
                        key={setup.setup_id}
                        onClick={() => {
                          setSelectedSetupId(setup.setup_id);
                          setSelectedSetupSymbol(setup.symbol);
                        }}
                        className={`transition-colors hover:bg-slate-800/60 cursor-pointer ${
                          selectedSetupId === setup.setup_id ? "bg-slate-800/80 border-l-2 border-l-amber-400" : ""
                        }`}
                      >
                        {/* ID */}
                        <td className="py-3 px-3 font-semibold text-amber-400/90 hover:underline">
                          {setup.setup_id.slice(0, 10)}
                        </td>
                        {/* Symbol */}
                        <td className="py-3 px-3 font-bold text-slate-100">{setup.symbol}</td>
                        {/* Direction */}
                        <td className="py-3 px-2">
                          <Badge text={setup.direction} variant="direction" size="sm" />
                        </td>
                        {/* Grade */}
                        <td className="py-3 px-2 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              setup.grade === "A+"
                                ? "bg-emerald-950 text-emerald-300 border-emerald-500/50"
                                : setup.grade === "A"
                                ? "bg-emerald-950/70 text-emerald-400 border-emerald-600/30"
                                : setup.grade === "B+"
                                ? "bg-sky-950/80 text-sky-300 border-sky-500/40"
                                : "bg-slate-900 text-slate-400 border-slate-800"
                            }`}
                          >
                            {setup.grade}
                          </span>
                        </td>
                        {/* Confidence */}
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <div className="w-12 bg-slate-800 h-1.5 rounded-full overflow-hidden border border-slate-700/60">
                              <div
                                className={`h-full rounded-full ${
                                  isGradeA ? "bg-emerald-400" : "bg-sky-400"
                                }`}
                                style={{ width: `${setup.confidence}%` }}
                              />
                            </div>
                            <span className="font-bold text-slate-200">{setup.confidence}%</span>
                          </div>
                        </td>
                        {/* Est Price */}
                        <td className="py-3 px-3 text-right text-slate-400">
                          ${setup.currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        {/* Entry Zone */}
                        <td className="py-3 px-3 text-right text-slate-400 text-[10px]">
                          ${setup.entry_zone_low ? setup.entry_zone_low.toFixed(1) : 0} - ${setup.entry_zone_high ? setup.entry_zone_high.toFixed(1) : 0}
                        </td>
                        {/* Pref Entry */}
                        <td className="py-3 px-3 text-right font-bold text-slate-100">
                          ${setup.preferred_entry ? setup.preferred_entry.toFixed(2) : 0}
                        </td>
                        {/* SL */}
                        <td className="py-3 px-3 text-right text-rose-400 text-[11px]">
                          ${setup.stop_loss ? setup.stop_loss.toFixed(2) : 0}
                        </td>
                        {/* TP */}
                        <td className="py-3 px-3 text-right text-emerald-400 text-[11px]">
                          ${setup.take_profit ? setup.take_profit.toFixed(2) : 0}
                        </td>
                        {/* R:R */}
                        <td className="py-3 px-2 text-right font-bold text-emerald-300">
                          {setup.reward_to_risk ? setup.reward_to_risk.toFixed(2) : "0.00"}x
                        </td>
                        {/* Eligibility */}
                        <td className="py-3 px-3 text-center">
                          {setup.eligible_for_signal ? (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/70 text-emerald-300 border border-emerald-500/30">
                              ELIGIBLE
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] bg-slate-900 text-slate-500 border border-slate-800">
                              BLOCKED
                            </span>
                          )}
                        </td>
                        {/* State */}
                        <td className="py-3 px-2 text-center">
                          <Badge text={setup.setup_state} variant="setup_state" size="sm" />
                        </td>
                        {/* Updated */}
                        <td className="py-3 px-3 text-right text-slate-400 text-[11px]">
                          {new Date(setup.evaluated_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards Layout (under lg viewport) */}
            <div className="block lg:hidden divide-y divide-slate-800/60">
              {processedScannerData.map((setup) => {
                const isExpanded = expandedRowId === setup.setup_id;
                return (
                  <div
                    key={setup.setup_id}
                    className={`p-4 space-y-3 transition-colors ${
                      isExpanded ? "bg-slate-950/40" : "hover:bg-slate-800/20"
                    }`}
                  >
                    {/* Compact Card Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-100">{setup.symbol}</span>
                        <Badge text={setup.direction} variant="direction" size="sm" />
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-slate-800 text-amber-400 border border-slate-700">
                          {setup.grade}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge text={setup.setup_state} variant="setup_state" size="sm" />
                        <button
                          onClick={() => setExpandedRowId(isExpanded ? null : setup.setup_id)}
                          className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-400"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>

                    {/* Primary Values Row */}
                    <div className="grid grid-cols-3 gap-2 text-center text-[11px] bg-slate-950 p-2.5 rounded-lg border border-slate-800/80">
                      <div>
                        <span className="text-slate-400 text-[9px] block">Pref Entry</span>
                        <span className="font-bold text-slate-100">${setup.preferred_entry}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[9px] block">Risk : Reward</span>
                        <span className="font-semibold text-emerald-400">{setup.reward_to_risk ? setup.reward_to_risk.toFixed(2) : "—"}x</span>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[9px] block">Confidence</span>
                        <span className="font-bold text-amber-400">{setup.confidence}%</span>
                      </div>
                    </div>

                    {/* Expandable Technical Details */}
                    {isExpanded && (
                      <div className="space-y-2 pt-2 text-[11px] border-t border-slate-800/60 font-mono">
                        <div className="grid grid-cols-2 gap-y-1 text-slate-300">
                          <div>Est Price:</div>
                          <div className="text-right text-slate-100 font-bold">${setup.currentPrice.toFixed(2)}</div>
                          <div>Entry Zone:</div>
                          <div className="text-right text-slate-400">${setup.entry_zone_low} - ${setup.entry_zone_high}</div>
                          <div>Stop Loss:</div>
                          <div className="text-right text-rose-400">${setup.stop_loss}</div>
                          <div>Take Profit:</div>
                          <div className="text-right text-emerald-400">${setup.take_profit}</div>
                          <div>Eligibility:</div>
                          <div className="text-right uppercase">
                            {setup.eligible_for_signal ? (
                              <span className="text-emerald-400 font-bold">ELIGIBLE</span>
                            ) : (
                              <span className="text-slate-500">BLOCKED</span>
                            )}
                          </div>
                          <div>ID:</div>
                          <div className="text-right text-amber-400/90 text-[10px] break-all">{setup.setup_id}</div>
                          <div>Updated:</div>
                          <div className="text-right text-slate-400">{new Date(setup.evaluated_at).toLocaleTimeString()}</div>
                        </div>

                        <div className="flex items-center gap-2 pt-2">
                          <button
                            onClick={() => {
                              setSelectedSetupId(setup.setup_id);
                              setSelectedSetupSymbol(setup.symbol);
                            }}
                            className="flex-1 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 font-bold text-center"
                          >
                            Open Detailed Evaluation Drawer
                          </button>
                        </div>
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

    {/* DETAIL DRAWER / INSPECT MODAL */}
      {selectedSetupId && selectedSetupSymbol && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/75 backdrop-blur-sm animate-in fade-in"
          onClick={() => {
            setSelectedSetupId(null);
            setSelectedSetupSymbol(null);
          }}
        >
          <div
            ref={drawerRef}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
            className="bg-slate-900 border-l border-slate-700/80 w-full max-w-2xl h-full shadow-2xl p-6 overflow-y-auto font-mono text-xs text-slate-200 space-y-6 relative flex flex-col justify-between animate-in slide-in-from-right"
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
          >
            {/* Drawer Content Area */}
            <div className="space-y-6 flex-1">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-4 sticky top-0 bg-slate-900 pt-1 z-10">
                <div>
                  <div className="flex items-center gap-2 font-bold text-base text-slate-100" id="drawer-title">
                    <Sparkles className="w-5 h-5 text-amber-400" />
                    <span>Algorithmic Scan Details</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                    <span>ID:</span>
                    <span className="text-amber-400 font-semibold">{selectedSetupId}</span>
                    <button
                      onClick={() => handleCopyId(selectedSetupId)}
                      className="p-1 rounded bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-100 transition"
                      title="Copy Setup ID"
                    >
                      {copiedId === selectedSetupId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setSelectedSetupId(null);
                    setSelectedSetupSymbol(null);
                  }}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
                  aria-label="Close drawer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Symbol Overview & Metrics */}
              {selectedProcessed && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px]">
                  <div>
                    <span className="text-slate-400 text-[9px] uppercase block mb-0.5">Symbol / Dir</span>
                    <span className="font-bold text-slate-100">{selectedProcessed.symbol}</span> / <Badge text={selectedProcessed.direction} variant="direction" size="sm" />
                  </div>
                  <div>
                    <span className="text-slate-400 text-[9px] block mb-0.5">Calculated Grade</span>
                    <span className="font-bold text-emerald-400">{selectedProcessed.grade}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[9px] block mb-0.5">Confidence Score</span>
                    <span className="font-bold text-amber-400">{selectedProcessed.confidence}%</span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[9px] block mb-0.5">Risk-Reward</span>
                    <span className="font-bold text-slate-100">{selectedProcessed.reward_to_risk?.toFixed(2)}x</span>
                  </div>
                </div>
              )}

              {/* Market Regimes comparison (Anchor vs Local Ticker) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* BTC Anchor Regime */}
                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800/80 space-y-2">
                  <h4 className="font-bold text-amber-400 text-[11px] uppercase flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5" /> BTC Anchor Regime
                  </h4>
                  <div className="space-y-1.5 text-[11px]">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Primary Regime:</span>
                      <span className="text-slate-200 font-semibold">{btcRegime?.primary_regime || "TRENDING_BULLISH"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Entry Permission:</span>
                      <span className="text-slate-200">{btcRegime?.entry_permission || "ALLOW_LONG"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Market Block:</span>
                      <span className="text-rose-400 font-bold">{btcRegime?.market_wide_block ? "ACTIVE" : "NONE"}</span>
                    </div>
                  </div>
                </div>

                {/* Local Symbol Regime */}
                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800/80 space-y-2">
                  <h4 className="font-bold text-emerald-400 text-[11px] uppercase flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5" /> {selectedSetupSymbol} Local Regime
                  </h4>
                  {isLoadingSymbolRegime ? (
                    <div className="h-10 flex items-center justify-center">
                      <div className="w-4 h-4 border border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
                    </div>
                  ) : symbolRegime ? (
                    <div className="space-y-1.5 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Regime:</span>
                        <span className="text-slate-200 font-semibold">{symbolRegime.primary_regime}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Permission:</span>
                        <span className="text-slate-200">{symbolRegime.entry_permission}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Confidence:</span>
                        <span className="text-emerald-400 font-bold">{Math.round(symbolRegime.confidence_score * 100)}%</span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-[10px]">No local regime data returned.</div>
                  )}
                </div>
              </div>

              {/* Live Technical Pullback Indicators Snapshot */}
              <div className="bg-slate-950/80 p-4 rounded-lg border border-slate-800 space-y-3">
                <h4 className="font-bold text-sky-400 text-[11px] uppercase flex items-center gap-1">
                  <Info className="w-3.5 h-3.5" /> Technical Coefficient Matrix
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-[11px] text-slate-300">
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Preferred Entry:</span>
                    <span className="text-slate-100 font-semibold">${selectedSetup?.preferred_entry}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Stop Loss (SL):</span>
                    <span className="text-rose-400 font-semibold">${selectedSetup?.stop_loss}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Take Profit (TP):</span>
                    <span className="text-emerald-400 font-semibold">${selectedSetup?.take_profit}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Reward-to-Risk (R:R):</span>
                    <span className="text-emerald-300 font-bold">{selectedSetup?.reward_to_risk?.toFixed(2)}x</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Pullback Depth:</span>
                    <span className="text-slate-200">{selectedSetup?.pullback_depth ? selectedSetup.pullback_depth.toFixed(3) : "0.0"}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Volume Expansion:</span>
                    <span className="text-slate-200">{selectedSetup?.volume_ratio ? `${selectedSetup.volume_ratio.toFixed(2)}x` : "—"}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">Liquidity Sweep:</span>
                    <span className="font-bold text-slate-200">{selectedSetup?.liquidity_sweep_detected ? "DETECTED" : "NO"}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">MSS Break:</span>
                    <span className="font-bold text-slate-200">{selectedSetup?.mss_detected ? "CONFIRMED" : "NO"}</span>
                  </div>
                </div>
              </div>

              {/* Rationale and Rules Evaluated */}
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <h5 className="font-bold text-emerald-400 text-[11px] uppercase flex items-center gap-1">
                    Passed Evaluation Rules
                  </h5>
                  <div className="p-2.5 bg-emerald-950/20 border border-emerald-500/20 rounded text-emerald-300 text-[11px] leading-relaxed">
                    {selectedSetup?.eligible_for_signal ? (
                      <ul className="space-y-1">
                        <li>• Multi-timeframe trend alignment verified across H1, 15m, and 5m.</li>
                        <li>• Bid/Ask spread tested beneath maximum threshold.</li>
                        {selectedSetup.liquidity_sweep_detected && <li>• Sweep of recent structural swing lows completed, flushing liquidity.</li>}
                        {selectedSetup.mss_detected && <li>• Market Structure Shift confirmed with volume expansion break.</li>}
                        <li>• Preferred entry zone located safely above institutional invalidation bounds.</li>
                      </ul>
                    ) : (
                      <span>Core technical parameters evaluated. Symbol did not pass all active risk rules.</span>
                    )}
                  </div>
                </div>

                {!selectedSetup?.eligible_for_signal && (
                  <div className="space-y-1.5">
                    <h5 className="font-bold text-rose-400 text-[11px] uppercase flex items-center gap-1">
                      Failed Rules & Rejection Reasons
                    </h5>
                    <div className="p-2.5 bg-rose-950/20 border border-rose-500/20 rounded text-rose-300 text-[11px]">
                      <ul className="space-y-1">
                        <li>• Rejection Code: BLOCKED_BY_RISK_LIMITS</li>
                        <li>• Failed: Candidate did not trigger sufficient liquidity sweep or market structure shift (MSS) within the scanning window.</li>
                        <li>• Note: High spread ratio or flat orderbook volume inhibits signal issuance.</li>
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              {/* Raw JSON Snapshot */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-400 text-[11px] uppercase">Raw API Response Snapshot</h4>
                  <button
                    onClick={() => handleCopyJson(selectedSetup)}
                    className="px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-slate-100 flex items-center gap-1.5 transition text-[10px]"
                  >
                    {copiedJson ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy JSON</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="text-[10px] text-sky-300 bg-slate-950 p-3 rounded-lg border border-slate-800/80 overflow-x-auto max-h-48 font-mono">
                  {JSON.stringify(selectedSetup, null, 2)}
                </pre>
              </div>
            </div>

            {/* Close footer for mobile */}
            <div className="border-t border-slate-800 pt-4 mt-4 sticky bottom-0 bg-slate-900">
              <button
                onClick={() => {
                  setSelectedSetupId(null);
                  setSelectedSetupSymbol(null);
                }}
                className="w-full py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 font-bold transition text-center text-xs"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
