import React, { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  Cell,
  CartesianGrid,
} from "recharts";
import { Candle, CandleTimeframe } from "../../api/types";
import { Clock, TrendingUp, TrendingDown, Layers } from "lucide-react";

/**
 * Safely formats a value as a string with a fixed number of decimals.
 * Gracefully handles non-finite or non-number values by falling back.
 */
const safeToFixed = (val: any, decimals = 2): string => {
  const num = Number(val);
  if (!Number.isFinite(num)) {
    return "0." + "0".repeat(decimals);
  }
  return num.toFixed(decimals);
};

interface CandleChartProps {
  candles: Candle[];
  symbol: string;
  currentTimeframe: CandleTimeframe;
  onTimeframeChange: (tf: CandleTimeframe) => void;
  isLoading?: boolean;
}

// Custom SVG Candlestick renderer for Recharts
const CustomCandleShape = (props: any) => {
  const { x, width, open, high, low, close, yAxisScale } = props;

  if (!yAxisScale || typeof x !== "number" || typeof width !== "number") return null;

  const openY = yAxisScale(open);
  const closeY = yAxisScale(close);
  const highY = yAxisScale(high);
  const lowY = yAxisScale(low);

  const isGreen = close >= open;
  const candleColor = isGreen ? "#10b981" : "#f43f5e";

  const candleTop = Math.min(openY, closeY);
  const candleHeight = Math.max(Math.abs(closeY - openY), 2); // At least 2px height
  const candleX = x + width * 0.15;
  const candleW = Math.max(width * 0.7, 3);
  const centerX = x + width / 2;

  return (
    <g className="transition-opacity hover:opacity-90">
      {/* High-Low Wick */}
      <line
        x1={centerX}
        y1={highY}
        x2={centerX}
        y2={lowY}
        stroke={candleColor}
        strokeWidth={1.2}
      />
      {/* Body Box */}
      <rect
        x={candleX}
        y={candleTop}
        width={candleW}
        height={candleHeight}
        fill={isGreen ? "#10b981" : "#f43f5e"}
        stroke={candleColor}
        strokeWidth={1}
        rx={1}
      />
    </g>
  );
};

export const CandleChart: React.FC<CandleChartProps> = ({
  candles,
  symbol,
  currentTimeframe,
  onTimeframeChange,
  isLoading = false,
}) => {
  // Candles arrive newest-first from API -> reverse for chronological left-to-right display
  const chronologicalCandles = [...candles].reverse();

  // Price Extrema calculations
  const prices = chronologicalCandles.flatMap((c) => [c.low_price, c.high_price]);
  const minPrice = prices.length ? Math.min(...prices) * 0.998 : 0;
  const maxPrice = prices.length ? Math.max(...prices) * 1.002 : 100;

  const latestCandle = chronologicalCandles[chronologicalCandles.length - 1];
  const firstCandle = chronologicalCandles[0];
  const priceChange =
    latestCandle && firstCandle
      ? latestCandle.close_price - firstCandle.open_price
      : 0;
  const priceChangePct =
    latestCandle && firstCandle && firstCandle.open_price > 0
      ? (priceChange / firstCandle.open_price) * 100
      : 0;

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 sm:p-5 shadow-xl flex flex-col gap-4">
      {/* Chart Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-800 border border-slate-700/60 text-slate-200">
            <Layers className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-slate-100 font-mono tracking-tight">
                {symbol}
              </span>
              <span className="text-xs font-mono text-slate-400 px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                {currentTimeframe}
              </span>
            </div>
            {latestCandle && (
              <div className="flex items-center gap-3 mt-0.5 text-xs font-mono">
                <span className="text-slate-300 font-semibold">
                  Last: ${latestCandle.close_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
                <span
                  className={`flex items-center gap-0.5 font-semibold ${
                    priceChange >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {priceChange >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                  {priceChange >= 0 ? "+" : ""}
                  {safeToFixed(priceChange, 2)} ({priceChangePct >= 0 ? "+" : ""}
                  {safeToFixed(priceChangePct, 2)}%)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Timeframe selector toggles */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 self-start sm:self-auto">
          <Clock className="w-3.5 h-3.5 text-slate-400 ml-2 mr-1" />
          {(["1m", "5m", "15m"] as CandleTimeframe[]).map((tf) => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={`px-3 py-1 rounded-md text-xs font-mono transition-all font-semibold ${
                currentTimeframe === tf
                  ? "bg-slate-800 text-emerald-300 border border-emerald-500/40 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Body */}
      {isLoading ? (
        <div className="h-80 w-full flex flex-col items-center justify-center gap-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
          <div className="w-7 h-7 border-2 border-slate-700 border-t-emerald-400 rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Rendering price candles...</span>
        </div>
      ) : chronologicalCandles.length === 0 ? (
        <div className="h-80 w-full flex items-center justify-center bg-slate-950/40 rounded-lg border border-slate-800/60 text-slate-400 text-xs font-mono">
          No candle telemetry available for {symbol} ({currentTimeframe})
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {/* Main Price Candlestick Chart */}
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chronologicalCandles}
                margin={{ top: 10, right: 10, left: 10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                <XAxis
                  dataKey="open_time"
                  tickFormatter={(val) => {
                    const d = new Date(val);
                    return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                  }}
                  stroke="#64748b"
                  tick={{ fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: "#334155" }}
                />
                <YAxis
                  domain={[minPrice, maxPrice]}
                  orientation="right"
                  stroke="#64748b"
                  tick={{ fontSize: 10, fontFamily: "monospace" }}
                  tickFormatter={(val) => val.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  axisLine={{ stroke: "#334155" }}
                  width={60}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data: Candle = payload[0].payload;
                      const isUp = data.close_price >= data.open_price;
                      return (
                        <div className="bg-slate-950/95 border border-slate-700 p-3 rounded-lg shadow-xl text-xs font-mono flex flex-col gap-1 text-slate-200 backdrop-blur-md">
                          <div className="text-slate-400 border-b border-slate-800 pb-1 mb-1 font-sans text-[11px]">
                            {new Date(data.open_time).toLocaleString()}
                          </div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                            <span className="text-slate-400">Open:</span>
                            <span className="text-right text-slate-100">${safeToFixed(data.open_price, 2)}</span>
                            <span className="text-slate-400">High:</span>
                            <span className="text-right text-emerald-400">${safeToFixed(data.high_price, 2)}</span>
                            <span className="text-slate-400">Low:</span>
                            <span className="text-right text-rose-400">${safeToFixed(data.low_price, 2)}</span>
                            <span className="text-slate-400">Close:</span>
                            <span className={`text-right font-bold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
                              ${safeToFixed(data.close_price, 2)}
                            </span>
                            <span className="text-slate-400">Volume:</span>
                            <span className="text-right text-sky-300">{data.volume.toLocaleString()}</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                {/* Render Candlesticks via custom shape overlay */}
                <Bar
                  dataKey="high_price"
                  shape={(props: any) => (
                    <CustomCandleShape
                      {...props}
                      open={props.payload.open_price}
                      close={props.payload.close_price}
                      high={props.payload.high_price}
                      low={props.payload.low_price}
                    />
                  )}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Volume Bar Sub-Chart */}
          <div className="h-20 w-full border-t border-slate-800/80 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chronologicalCandles} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                <YAxis orientation="right" stroke="#64748b" tick={{ fontSize: 9, fontFamily: "monospace" }} width={60} />
                <Bar dataKey="volume">
                  {chronologicalCandles.map((c, idx) => (
                    <Cell
                      key={`vol-${idx}`}
                      fill={c.close_price >= c.open_price ? "rgba(16, 185, 129, 0.4)" : "rgba(244, 63, 94, 0.4)"}
                      stroke={c.close_price >= c.open_price ? "#10b981" : "#f43f5e"}
                      strokeWidth={0.5}
                    />
                  ))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};
