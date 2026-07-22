import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  BookOpen,
  Calendar,
  ShieldAlert,
  SlidersHorizontal,
  RefreshCw,
  Search,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  X,
  TrendingUp,
  Award,
} from "lucide-react";

export const TradeJournalPage: React.FC = () => {
  const isTabVisible = useTabVisibility();
  const [filterSymbol, setFilterSymbol] = useState("");
  const [filterDirection, setFilterDirection] = useState("ALL");
  const [filterResult, setFilterResult] = useState("ALL");
  const [selectedTrade, setSelectedTrade] = useState<any | null>(null);

  // Fetch health to see if backend is online
  const { data: health, isLoading: isLoadingHealth } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
  });

  // Fetch trade journal data
  const {
    data: journalData,
    isLoading: isLoadingJournal,
    isError: isErrorJournal,
    error: errorJournal,
    refetch: refetchJournal,
    isFetching: isFetchingJournal,
  } = useQuery({
    queryKey: ["tradeJournal"],
    queryFn: () => apiClient.getTradeJournal(),
    refetchInterval: isTabVisible ? 15000 : false,
    retry: 1,
  });

  // Check if backend does not support the endpoint (404 status)
  const isNotSupported =
    (errorJournal as any)?.status === 404 ||
    (errorJournal as any)?.message?.includes("404") ||
    (errorJournal as any)?.message?.toLowerCase().includes("not found");

  const isOffline = !isLoadingHealth && !health;

  // Process and filter trades if supported and returned
  const trades = Array.isArray(journalData)
    ? journalData
    : journalData?.trades || [];

  const filteredTrades = trades.filter((trade: any) => {
    const matchesSymbol = trade.symbol
      ? trade.symbol.toLowerCase().includes(filterSymbol.toLowerCase())
      : true;
    const matchesDirection =
      filterDirection === "ALL" || trade.direction === filterDirection;
    const isWin = trade.pnl > 0 || trade.result === "WIN";
    const matchesResult =
      filterResult === "ALL" ||
      (filterResult === "WIN" && isWin) ||
      (filterResult === "LOSS" && !isWin);
    return matchesSymbol && matchesDirection && matchesResult;
  });

  // Performance metrics calculation if we have trades
  const wins = trades.filter((t: any) => t.pnl > 0 || t.result === "WIN");
  const winRate = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;
  const netPnL = trades.reduce((acc: number, t: any) => acc + (t.pnl || 0), 0);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto animate-in fade-in" id="trade-journal-page">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5 font-mono">
            <BookOpen className="w-6 h-6 text-amber-500" />
            TRADE JOURNAL
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            Historical ledger and performance analysis of closed trades
          </p>
        </div>

        <button
          onClick={() => refetchJournal()}
          disabled={isLoadingJournal || isFetchingJournal}
          className="self-start sm:self-center p-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 hover:text-slate-100 hover:border-slate-700 transition disabled:opacity-50"
          title="Refresh trade journal"
        >
          <RefreshCw className={`w-4 h-4 ${isFetchingJournal ? "animate-spin text-amber-400" : ""}`} />
        </button>
      </div>

      {/* Main Content States */}
      {isLoadingJournal || isLoadingHealth ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4" id="journal-loading">
          <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
          <p className="text-xs font-mono text-slate-400 tracking-wider">
            RETRIEVING HISTORICAL LEDGER DATA...
          </p>
        </div>
      ) : isNotSupported ? (
        <div className="py-12 px-6" id="journal-not-supported">
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-8 max-w-xl mx-auto text-center space-y-4 shadow-xl">
            <div className="w-12 h-12 bg-amber-950/40 rounded-xl border border-amber-500/20 flex items-center justify-center mx-auto">
              <ShieldAlert className="w-6 h-6 text-amber-500" />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-mono font-bold text-slate-200 uppercase tracking-wider">
                Feature Unavailable
              </h3>
              <p className="text-xs font-mono text-slate-400 leading-relaxed">
                Trade journal data is not available in the current backend.
              </p>
            </div>
          </div>
        </div>
      ) : isErrorJournal || isOffline ? (
        <div className="py-12" id="journal-error">
          <ErrorMessage
            title="Journal Offline"
            message="We were unable to load historical trade journal data from the backend. The service might be offline or undergoing maintenance."
            error={errorJournal || new Error("Backend connection offline.")}
            onRetry={() => refetchJournal()}
            isRetrying={isFetchingJournal}
          />
        </div>
      ) : trades.length === 0 ? (
        <div className="space-y-6" id="journal-empty-state">
          {/* Performance Summary Banner */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-1">
              <span className="text-slate-400">Total Closed Trades</span>
              <div className="text-lg font-bold text-slate-100">0</div>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-1">
              <span className="text-slate-400">Net Realized Profit</span>
              <div className="text-lg font-bold text-slate-100">$0.00</div>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 font-mono text-xs space-y-1">
              <span className="text-slate-400">Win Rate</span>
              <div className="text-lg font-bold text-slate-100">0.0%</div>
            </div>
          </div>

          <div className="bg-slate-900/20 border border-slate-800/60 border-dashed rounded-xl py-16 text-center max-w-2xl mx-auto space-y-3">
            <div className="w-10 h-10 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-center mx-auto">
              <BookOpen className="w-5 h-5 text-slate-500" />
            </div>
            <div className="space-y-1">
              <p className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                No Trade History
              </p>
              <p className="text-xs font-mono text-slate-400 max-w-sm mx-auto leading-relaxed">
                There are no historical demo trades recorded in this system database. All closed algorithmic setups will populate here once completed.
              </p>
            </div>
          </div>
        </div>
      ) : (
        /* Real data presentation (if supported and contains data) */
        <div className="space-y-6" id="journal-real-data">
          {/* Performance Summary Header */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-1">
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Total Trades
              </div>
              <div className="text-xl font-bold font-mono text-slate-100">
                {trades.length}
              </div>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-1">
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Realized Net PnL
              </div>
              <div className={`text-xl font-bold font-mono ${netPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {netPnL >= 0 ? "+" : ""}${netPnL.toFixed(2)}
              </div>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-1">
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Win Rate
              </div>
              <div className="text-xl font-bold font-mono text-amber-400 flex items-center gap-1.5">
                <Award className="w-5 h-5 text-amber-500 inline" />
                {winRate.toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Filters Bar */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3 font-mono text-xs">
            <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Filter className="w-4 h-4 text-amber-400" />
              Journal Filters
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Symbol search */}
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search symbol..."
                  value={filterSymbol}
                  onChange={(e) => setFilterSymbol(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/50"
                />
              </div>

              {/* Direction selector */}
              <select
                value={filterDirection}
                onChange={(e) => setFilterDirection(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/50 cursor-pointer"
              >
                <option value="ALL">ALL DIRECTIONS</option>
                <option value="LONG">LONG</option>
                <option value="SHORT">SHORT</option>
              </select>

              {/* Result selector */}
              <select
                value={filterResult}
                onChange={(e) => setFilterResult(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500/50 cursor-pointer"
              >
                <option value="ALL">ALL OUTCOMES</option>
                <option value="WIN">WIN ONLY</option>
                <option value="LOSS">LOSS ONLY</option>
              </select>
            </div>
          </div>

          {/* Table list */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-3">
              <SlidersHorizontal className="w-4 h-4 text-sky-400" />
              Closed Demo Trades ({filteredTrades.length})
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4 font-semibold">Symbol</th>
                    <th className="py-3 px-4 font-semibold">Strategy</th>
                    <th className="py-3 px-4 font-semibold">Direction</th>
                    <th className="py-3 px-4 font-semibold">Entry</th>
                    <th className="py-3 px-4 font-semibold">Exit</th>
                    <th className="py-3 px-4 font-semibold">R:R</th>
                    <th className="py-3 px-4 font-semibold">Result</th>
                    <th className="py-3 px-4 font-semibold text-right">Realized PnL</th>
                    <th className="py-3 px-4 font-semibold"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredTrades.map((trade: any, idx: number) => {
                    const isLong = trade.direction === "LONG";
                    const isWin = trade.pnl > 0 || trade.result === "WIN";
                    return (
                      <tr
                        key={trade.id || idx}
                        onClick={() => setSelectedTrade(trade)}
                        className="hover:bg-slate-900/40 text-slate-200 transition cursor-pointer"
                      >
                        <td className="py-3 px-4 font-bold">{trade.symbol}</td>
                        <td className="py-3 px-4 text-slate-400">{trade.strategy || "Trend Pullback"}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              isLong ? "bg-emerald-950/60 text-emerald-400" : "bg-rose-950/60 text-rose-400"
                            }`}
                          >
                            {trade.direction}
                          </span>
                        </td>
                        <td className="py-3 px-4">${trade.entry_price?.toLocaleString()}</td>
                        <td className="py-3 px-4">${trade.exit_price?.toLocaleString()}</td>
                        <td className="py-3 px-4 text-slate-400">{trade.risk_reward || trade.rr || "1:2.0"}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              isWin
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            }`}
                          >
                            {isWin ? "WIN" : "LOSS"}
                          </span>
                        </td>
                        <td className={`py-3 px-4 text-right font-bold ${isWin ? "text-emerald-400" : "text-rose-400"}`}>
                          {isWin ? "+" : ""}${trade.pnl?.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-500">
                          <ChevronRight className="w-4 h-4 ml-auto" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Details drawer */}
      {selectedTrade && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm animate-in fade-in"
          id="trade-details-drawer"
        >
          <div className="bg-slate-900 border-l border-slate-700/80 w-full max-w-lg h-full shadow-2xl p-6 overflow-y-auto font-mono text-xs text-slate-200 space-y-6 relative animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-amber-500" />
                  TRADE AUDIT LEDGER
                </h3>
                <span className="text-[10px] text-slate-400">ID: {selectedTrade.id || "N/A"}</span>
              </div>
              <button
                onClick={() => setSelectedTrade(null)}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Audit metrics */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                <div className="text-[10px] text-slate-500 uppercase">Symbol</div>
                <div className="text-xs font-bold text-slate-100">{selectedTrade.symbol}</div>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                <div className="text-[10px] text-slate-500 uppercase">Strategy</div>
                <div className="text-xs font-bold text-slate-100">{selectedTrade.strategy || "Trend Pullback"}</div>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                <div className="text-[10px] text-slate-500 uppercase">Direction</div>
                <div className="text-xs font-bold text-slate-100">{selectedTrade.direction}</div>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                <div className="text-[10px] text-slate-500 uppercase">PnL Result</div>
                <div className={`text-xs font-bold ${selectedTrade.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  ${selectedTrade.pnl?.toFixed(2)} ({selectedTrade.result || (selectedTrade.pnl >= 0 ? "WIN" : "LOSS")})
                </div>
              </div>
            </div>

            {/* Detailed execution specifications */}
            <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-3.5">
              <h4 className="font-bold text-slate-300 border-b border-slate-800 pb-2">EXECUTION TIMELINE</h4>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">Entry Price:</span>
                  <span className="font-bold text-slate-200">${selectedTrade.entry_price?.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Exit Price:</span>
                  <span className="font-bold text-slate-200">${selectedTrade.exit_price?.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Stop Loss:</span>
                  <span className="text-rose-400">${selectedTrade.stop_loss?.toLocaleString() || "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Take Profit:</span>
                  <span className="text-emerald-400">${selectedTrade.take_profit?.toLocaleString() || "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Risk Reward Ratio:</span>
                  <span className="text-slate-300 font-bold">{selectedTrade.risk_reward || selectedTrade.rr || "1:2.0"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Opened At:</span>
                  <span className="text-slate-400">{selectedTrade.opened_at ? new Date(selectedTrade.opened_at).toLocaleString() : "N/A"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Closed At:</span>
                  <span className="text-slate-400">{selectedTrade.closed_at ? new Date(selectedTrade.closed_at).toLocaleString() : "N/A"}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
