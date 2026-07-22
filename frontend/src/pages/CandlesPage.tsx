import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { CandleTimeframe, MarketSymbol } from "../api/types";
import { useSymbol } from "../context/SymbolContext";
import { useTabVisibility } from "../hooks/useTabVisibility";
import { CandleChart } from "../components/common/CandleChart";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  BarChart2,
  Search,
  RefreshCw,
  Coins,
  ArrowUpDown,
  Zap,
  TrendingUp,
  Clock,
  Layers,
} from "lucide-react";

export const CandlesPage: React.FC = () => {
  const { selectedSymbol, setSelectedSymbol } = useSymbol();
  const [timeframe, setTimeframe] = useState<CandleTimeframe>("5m");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const isTabVisible = useTabVisibility();

  // Poll Symbols table
  const {
    data: symbols = [],
    isLoading: isLoadingSymbols,
    isError: isErrorSymbols,
    error: errorSymbols,
    refetch: refetchSymbols,
  } = useQuery({
    queryKey: ["symbolsList"],
    queryFn: () => apiClient.getSymbols(true, 100),
    staleTime: 60000,
    retry: 1,
  });

  // Poll selected symbol snapshot every 5s (paused if tab is hidden)
  const {
    data: snapshot,
    isLoading: isLoadingSnapshot,
    isError: isErrorSnapshot,
    error: errorSnapshot,
    refetch: refetchSnapshot,
    isFetching: isFetchingSnapshot,
  } = useQuery({
    queryKey: ["snapshot", selectedSymbol],
    queryFn: () => apiClient.getSnapshot(selectedSymbol),
    refetchInterval: isTabVisible ? 5000 : false,
    retry: 1,
  });

  // Poll candles every 5s (paused if tab is hidden)
  const {
    data: candles = [],
    isLoading: isLoadingCandles,
    isError: isErrorCandles,
    error: errorCandles,
    refetch: refetchCandles,
  } = useQuery({
    queryKey: ["candles", selectedSymbol, timeframe],
    queryFn: () => apiClient.getCandles(selectedSymbol, timeframe, 200),
    refetchInterval: isTabVisible ? 5000 : false,
    retry: 1,
  });

  const isError = isErrorSymbols || isErrorSnapshot || isErrorCandles;
  const anyError = errorSymbols || errorSnapshot || errorCandles;
  const isRetrying = isFetchingSnapshot;

  const filteredSymbols = symbols.filter(
    (s) =>
      s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.base_asset.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 font-mono tracking-tight flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-amber-400 inline" /> SYMBOLS & CANDLES TERMINAL
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Order book depth, price action candles, and exchange precision limits for active trading pairs.
          </p>
        </div>
      </div>

      {isError ? (
        <div className="py-12">
          <ErrorMessage
            title="Market Data Stream Unavailable"
            message="We were unable to load market symbols or candlestick feeds from the backend. The service might be offline or undergoing maintenance."
            error={anyError}
            onRetry={() => {
              refetchSymbols();
              refetchSnapshot();
              refetchCandles();
            }}
            isRetrying={isRetrying}
          />
        </div>
      ) : (
        <>
          {/* Top Orderbook Snapshot Bar for Selected Symbol */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-slate-100">
            <Zap className="w-4 h-4 text-amber-400" />
            <span>ORDERBOOK SNAPSHOT: {selectedSymbol}</span>
          </div>
          {snapshot && (
            <span className="text-[10px] font-mono text-slate-400">
              Snapshot Time: {new Date(snapshot.snapshot_at).toLocaleTimeString()}
            </span>
          )}
        </div>

        {isLoadingSnapshot ? (
          <div className="h-12 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-amber-400 rounded-full animate-spin" />
          </div>
        ) : snapshot ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs tabular-nums">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 uppercase block font-semibold mb-1">Bid Price / Qty</span>
              <div className="font-bold text-emerald-400 text-sm">
                ${snapshot.bid_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Qty: {snapshot.bid_quantity}</div>
            </div>

            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 uppercase block font-semibold mb-1">Ask Price / Qty</span>
              <div className="font-bold text-rose-400 text-sm">
                ${snapshot.ask_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Qty: {snapshot.ask_quantity}</div>
            </div>

            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 uppercase block font-semibold mb-1">Spread (Basis Points)</span>
              <div className="font-bold text-amber-400 text-sm">{snapshot.spread_bps} bps</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Limit: &le; 8.0 bps</div>
            </div>

            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-400 uppercase block font-semibold mb-1">Last Executed</span>
              <div className="font-bold text-slate-100 text-sm">
                ${snapshot.last_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Exchange Feed</div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Main Chart Component */}
      <CandleChart
        candles={candles}
        symbol={selectedSymbol}
        currentTimeframe={timeframe}
        onTimeframeChange={(tf) => setTimeframe(tf)}
        isLoading={isLoadingCandles}
      />

      {/* Symbols Precision & Limits Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3 font-mono">
          <div>
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Coins className="w-4 h-4 text-emerald-400" /> ACTIVE TRADING PAIRS & EXCHANGE LIMITS ({filteredSymbols.length})
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">Select a symbol to load live candles and depth snapshot.</p>
          </div>

          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent text-slate-100 placeholder-slate-500 w-32 focus:outline-none font-mono"
            />
          </div>
        </div>

        {isLoadingSymbols ? (
          <div className="p-8 text-center font-mono text-xs text-slate-400">Loading symbols dictionary...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs font-mono tabular-nums">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Assets</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Tick Size</th>
                  <th className="py-2.5 px-3 text-right">Step Size</th>
                  <th className="py-2.5 px-3 text-right">Min Qty</th>
                  <th className="py-2.5 px-3 text-right">Min Notional</th>
                  <th className="py-2.5 px-3 text-center">Price Prec</th>
                  <th className="py-2.5 px-3 text-center">Qty Prec</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {filteredSymbols.map((sym) => (
                  <tr
                    key={sym.symbol}
                    onClick={() => setSelectedSymbol(sym.symbol)}
                    className={`transition-colors hover:bg-slate-800/60 cursor-pointer ${
                      selectedSymbol === sym.symbol ? "bg-slate-800/80 font-bold border-l-2 border-l-amber-400" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3 font-bold text-amber-400">{sym.symbol}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {sym.base_asset}/{sym.quote_asset}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/40">
                        {sym.trading_status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-300">{sym.tick_size}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">{sym.step_size}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">{sym.minimum_quantity}</td>
                    <td className="py-2.5 px-3 text-right text-slate-300">${sym.minimum_notional}</td>
                    <td className="py-2.5 px-3 text-center text-slate-400">{sym.price_precision}</td>
                    <td className="py-2.5 px-3 text-center text-slate-400">{sym.quantity_precision}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
};
