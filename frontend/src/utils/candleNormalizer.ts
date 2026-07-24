import { Candle } from "../api/types";

/**
 * Normalizes all candle numeric fields immediately after the API response.
 * Converts open_price, high_price, low_price, close_price, and volume to finite numbers.
 * Discards/rejects candles with non-finite values or missing critical numeric data.
 */
export function normalizeCandle(candle: any): Candle | null {
  if (!candle || typeof candle !== "object") {
    return null;
  }

  try {
    const open_price = Number(candle.open_price);
    const high_price = Number(candle.high_price);
    const low_price = Number(candle.low_price);
    const close_price = Number(candle.close_price);
    const volume = Number(candle.volume);

    // Reject non-finite values
    if (
      !Number.isFinite(open_price) ||
      !Number.isFinite(high_price) ||
      !Number.isFinite(low_price) ||
      !Number.isFinite(close_price) ||
      !Number.isFinite(volume)
    ) {
      return null;
    }

    // Return normalized candle, retaining other fields but overwriting normalized numbers
    return {
      ...candle,
      open_price,
      high_price,
      low_price,
      close_price,
      volume,
      quote_volume: candle.quote_volume !== undefined ? Number(candle.quote_volume) : 0,
      trade_count: candle.trade_count !== undefined ? Number(candle.trade_count) : 0,
    };
  } catch {
    return null;
  }
}

/**
 * Normalizes an array of candles, filtering out any invalid or non-finite candles.
 */
export function normalizeCandles(candles: any[]): Candle[] {
  if (!Array.isArray(candles)) {
    return [];
  }
  return candles
    .map(normalizeCandle)
    .filter((c): c is Candle => c !== null);
}
