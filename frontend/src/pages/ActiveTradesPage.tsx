import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  TrendingUp,
  Clock,
  ShieldAlert,
  Layers,
  RefreshCw,
  Zap,
  Play,
  Pause,
  HelpCircle,
} from "lucide-react";

export const ActiveTradesPage: React.FC = () => {
  const isTabVisible = useTabVisibility();

  // Fetch health to see if the system is online
  const { data: health, isLoading: isLoadingHealth } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
  });

  // Fetch active trades
  const {
    data: activeTrades,
    isLoading: isLoadingTrades,
    isError: isErrorTrades,
    error: errorTrades,
    refetch: refetchTrades,
    isFetching: isFetchingTrades,
  } = useQuery({
    queryKey: ["activeTrades"],
    queryFn: () => apiClient.getActiveTrades(),
    refetchInterval: isTabVisible ? 10000 : false,
    retry: 1,
  });

  const isDemoTradingEnabled = health?.demo_trading?.status === "enabled";
  const isExecutionEnabled = health?.execution?.status === "enabled";

  // Check if backend does not support the endpoint (404 status)
  const isNotSupported =
    (errorTrades as any)?.status === 404 ||
    (errorTrades as any)?.message?.includes("404") ||
    (errorTrades as any)?.message?.toLowerCase().includes("not found");

  const isOffline = !isLoadingHealth && !health;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" id="active-trades-page">
      {/* Header section with Demo Trading Badge */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5 font-mono">
            <Layers className="w-6 h-6 text-amber-500 animate-pulse" />
            ACTIVE TRADES
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-1">
            Real-time terminal execution & position tracker
          </p>
        </div>

        {/* Demo Trading Badge / Controls */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-mono text-xs font-bold ${
              isDemoTradingEnabled
                ? "bg-amber-950/40 border-amber-500/30 text-amber-400"
                : "bg-slate-900 border-slate-800 text-slate-400"
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${isDemoTradingEnabled ? "animate-pulse" : ""}`} />
            <span>DEMO TRADING: {isDemoTradingEnabled ? "ENABLED" : "DISABLED"}</span>
          </div>

          <button
            onClick={() => refetchTrades()}
            disabled={isLoadingTrades || isFetchingTrades}
            className="p-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 hover:text-slate-100 hover:border-slate-700 transition disabled:opacity-50"
            title="Refresh positions feed"
          >
            <RefreshCw className={`w-4 h-4 ${isFetchingTrades ? "animate-spin text-amber-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Content States */}
      {isLoadingTrades || isLoadingHealth ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4" id="trades-loading">
          <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
          <p className="text-xs font-mono text-slate-400 tracking-wider">
            SYNCHRONIZING PORTFOLIO STATE...
          </p>
        </div>
      ) : isNotSupported ? (
        <div className="py-12 px-6" id="trades-not-supported">
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-8 max-w-xl mx-auto text-center space-y-4 shadow-xl">
            <div className="w-12 h-12 bg-amber-950/40 rounded-xl border border-amber-500/20 flex items-center justify-center mx-auto">
              <ShieldAlert className="w-6 h-6 text-amber-500" />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-mono font-bold text-slate-200 uppercase tracking-wider">
                Feature Unvailable
              </h3>
              <p className="text-xs font-mono text-slate-400 leading-relaxed">
                Active trade monitoring is not available in the current backend.
              </p>
            </div>
          </div>
        </div>
      ) : isErrorTrades || isOffline ? (
        <div className="py-12" id="trades-error">
          <ErrorMessage
            title="Portfolio Stream Offline"
            message="We were unable to establish a connection to the active trade tracking socket. The engine server might be restarting or offline."
            error={errorTrades || new Error("Backend connection offline.")}
            onRetry={() => refetchTrades()}
            isRetrying={isFetchingTrades}
          />
        </div>
      ) : !activeTrades || activeTrades.length === 0 ? (
        <div className="space-y-6" id="trades-empty-state">
          {/* Execution Status Banner */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 font-mono text-xs">
            <div className="flex items-center gap-2.5">
              <div className={`w-2 h-2 rounded-full ${isExecutionEnabled ? "bg-emerald-500 animate-pulse" : "bg-slate-500"}`} />
              <span className="text-slate-400">Execution Status:</span>
              <span className={isExecutionEnabled ? "text-emerald-400 font-bold" : "text-slate-400"}>
                {isExecutionEnabled ? "LIVE AUTO-TRADING ACTIVE" : "PAUSED"}
              </span>
            </div>
            <div className="text-slate-400 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" />
              <span>Checked just now</span>
            </div>
          </div>

          {/* Empty Positions Box */}
          <div className="bg-slate-900/20 border border-slate-800/60 border-dashed rounded-xl py-16 text-center max-w-2xl mx-auto space-y-3">
            <div className="w-10 h-10 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-center mx-auto">
              <TrendingUp className="w-5 h-5 text-slate-500" />
            </div>
            <div className="space-y-1">
              <p className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
                No Active Trades
              </p>
              <p className="text-xs font-mono text-slate-400 max-w-sm mx-auto leading-relaxed">
                There are currently no active open positions or pending orders in progress. The scanner is continuously scanning for setups.
              </p>
            </div>
          </div>
        </div>
      ) : (
        /* Real data presentation (if supported and contains data) */
        <div className="space-y-8" id="trades-real-data">
          {/* Open Positions Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Open Demo Positions ({activeTrades.positions?.length || 0})
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4 font-semibold">Symbol</th>
                    <th className="py-3 px-4 font-semibold">Direction</th>
                    <th className="py-3 px-4 font-semibold">Qty</th>
                    <th className="py-3 px-4 font-semibold">Entry Price</th>
                    <th className="py-3 px-4 font-semibold">Current Price</th>
                    <th className="py-3 px-4 font-semibold">Stop Loss</th>
                    <th className="py-3 px-4 font-semibold">Take Profit</th>
                    <th className="py-3 px-4 font-semibold text-right">Realized PnL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {activeTrades.positions?.map((pos: any, idx: number) => {
                    const isLong = pos.direction === "LONG" || pos.direction === "BUY";
                    const isProfit = pos.pnl >= 0;
                    return (
                      <tr key={pos.id || idx} className="hover:bg-slate-900/40 text-slate-200 transition">
                        <td className="py-3 px-4 font-bold">{pos.symbol}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              isLong
                                ? "bg-emerald-950/60 text-emerald-400 border border-emerald-500/20"
                                : "bg-rose-950/60 text-rose-400 border border-rose-500/20"
                            }`}
                          >
                            {pos.direction}
                          </span>
                        </td>
                        <td className="py-3 px-4">{pos.quantity || pos.qty}</td>
                        <td className="py-3 px-4">${pos.entry_price?.toLocaleString() || pos.entry?.toLocaleString()}</td>
                        <td className="py-3 px-4">${pos.current_price?.toLocaleString()}</td>
                        <td className="py-3 px-4 text-rose-400">${pos.stop_loss?.toLocaleString() || pos.sl?.toLocaleString()}</td>
                        <td className="py-3 px-4 text-emerald-400">${pos.take_profit?.toLocaleString() || pos.tp?.toLocaleString()}</td>
                        <td className={`py-3 px-4 text-right font-bold ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
                          {isProfit ? "+" : ""}${pos.pnl?.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pending Demo Orders */}
          {activeTrades.orders && activeTrades.orders.length > 0 && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
              <div className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider border-b border-slate-800 pb-3">
                Pending Demo Orders ({activeTrades.orders.length})
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse font-mono text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4 font-semibold">Symbol</th>
                      <th className="py-3 px-4 font-semibold">Type</th>
                      <th className="py-3 px-4 font-semibold">Direction</th>
                      <th className="py-3 px-4 font-semibold">Price</th>
                      <th className="py-3 px-4 font-semibold">Qty</th>
                      <th className="py-3 px-4 font-semibold">Created At</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {activeTrades.orders.map((order: any, idx: number) => {
                      const isLong = order.direction === "LONG" || order.direction === "BUY";
                      return (
                        <tr key={order.id || idx} className="hover:bg-slate-900/40 text-slate-200 transition">
                          <td className="py-3 px-4 font-bold">{order.symbol}</td>
                          <td className="py-3 px-4 text-slate-400">{order.type}</td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                isLong ? "bg-emerald-950 text-emerald-400" : "bg-rose-950 text-rose-400"
                              }`}
                            >
                              {order.direction}
                            </span>
                          </td>
                          <td className="py-3 px-4">${order.price?.toLocaleString()}</td>
                          <td className="py-3 px-4">{order.quantity || order.qty}</td>
                          <td className="py-3 px-4 text-slate-400">{new Date(order.created_at).toLocaleString()}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
