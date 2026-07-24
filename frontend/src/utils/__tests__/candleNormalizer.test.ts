import { describe, it, expect } from "vitest";
import { normalizeCandle, normalizeCandles } from "../candleNormalizer";

describe("Candle Normalizer Regression Tests", () => {
  it("should successfully normalize string-form numeric values to standard numbers", () => {
    const rawCandle = {
      symbol: "BTCUSDT",
      timeframe: "5m",
      open_time: "2025-01-01T00:00:00Z",
      close_time: "2025-01-01T00:05:00Z",
      open_price: "50000.50",
      high_price: "50100.25",
      low_price: "49950.00",
      close_price: "50050.75",
      volume: "123.456",
      quote_volume: "6178125.00",
      trade_count: "500",
    };

    const normalized = normalizeCandle(rawCandle);
    expect(normalized).not.toBeNull();
    expect(normalized?.open_price).toBe(50000.50);
    expect(normalized?.high_price).toBe(50100.25);
    expect(normalized?.low_price).toBe(49950.00);
    expect(normalized?.close_price).toBe(50050.75);
    expect(normalized?.volume).toBe(123.456);
    expect(normalized?.quote_volume).toBe(6178125.00);
    expect(normalized?.trade_count).toBe(500);
  });

  it("should retain valid standard numeric candle values intact", () => {
    const rawCandle = {
      symbol: "ETHUSDT",
      timeframe: "1m",
      open_time: "2025-01-01T00:00:00Z",
      close_time: "2025-01-01T00:01:00Z",
      open_price: 3000.50,
      high_price: 3010.00,
      low_price: 2995.00,
      close_price: 3005.25,
      volume: 45.67,
      quote_volume: 137000.0,
      trade_count: 120,
    };

    const normalized = normalizeCandle(rawCandle);
    expect(normalized).not.toBeNull();
    expect(normalized?.open_price).toBe(3000.50);
    expect(normalized?.high_price).toBe(3010.00);
    expect(normalized?.low_price).toBe(2995.00);
    expect(normalized?.close_price).toBe(3005.25);
    expect(normalized?.volume).toBe(45.67);
  });

  it("should reject candles with non-finite values (NaN, Infinity, -Infinity)", () => {
    const candleWithNaN = {
      symbol: "BTCUSDT",
      open_price: "50000.0",
      high_price: "NaN",
      low_price: "49900.0",
      close_price: "50100.0",
      volume: "10.0",
    };

    const candleWithInfinity = {
      symbol: "BTCUSDT",
      open_price: "50000.0",
      high_price: "50500.0",
      low_price: "-Infinity",
      close_price: "50100.0",
      volume: "10.0",
    };

    expect(normalizeCandle(candleWithNaN)).toBeNull();
    expect(normalizeCandle(candleWithInfinity)).toBeNull();
  });

  it("should filter out invalid candles when normalizing an array of candles", () => {
    const candles = [
      {
        symbol: "BTCUSDT",
        open_price: "50000.0",
        high_price: "50500.0",
        low_price: "49900.0",
        close_price: "50100.0",
        volume: "10.0",
      },
      {
        symbol: "BTCUSDT",
        open_price: "50000.0",
        high_price: "invalid_number",
        low_price: "49900.0",
        close_price: "50100.0",
        volume: "10.0",
      },
      {
        symbol: "BTCUSDT",
        open_price: 50100.0,
        high_price: 50600.0,
        low_price: 50000.0,
        close_price: 50200.0,
        volume: 12.5,
      },
    ];

    const result = normalizeCandles(candles);
    expect(result.length).toBe(2);
    expect(result[0].open_price).toBe(50000.0);
    expect(result[1].open_price).toBe(50100.0);
  });
});
