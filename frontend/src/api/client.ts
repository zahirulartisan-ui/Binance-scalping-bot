import {
  Candle,
  CandleTimeframe,
  FastAPIError,
  HealthStatusResponse,
  MarketDataStatusResponse,
  MarketRegimeResponse,
  MarketSnapshot,
  MarketSymbol,
  ActiveTradesResponse,
  RuntimeSettings,
  RuntimeSettingsPatch,
  StrategyInfo,
  StrategySetup,
  TelemetryFeedResponse,
  TradeJournalResponse,
  TrendPullbackEvaluation,
} from "./types";
import { normalizeCandles } from "../utils/candleNormalizer";

/**
 * Validates and retrieves the API Base URL.
 * Ensures VITE_API_BASE_URL is a valid HTTP/HTTPS URL.
 */
export const getApiBaseUrl = (): string => {
  const env = (import.meta as any).env;
  const url = env?.VITE_API_BASE_URL || "http://localhost:8000";

  if (!url) {
    throw new Error("Configuration Error: VITE_API_BASE_URL is empty or undefined.");
  }

  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("URL must start with http:// or https://");
    }
  } catch (e: any) {
    throw new Error(`Configuration Error: Invalid VITE_API_BASE_URL format: "${url}". details: ${e?.message || "Invalid URL"}`);
  }

  return url.replace(/\/+$/, "");
};

/**
 * Parses and handles the FastAPI standard errors.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorData: FastAPIError = await res.json();
      if (typeof errorData.detail === "string") {
        errorDetail = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorDetail = errorData.detail.map((e) => e.msg).join("; ");
      }
    } catch {
      // Ignore JSON parse error on non-JSON error responses
    }
    const err = new Error(errorDetail) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

/**
 * Main API Client for the scalping bot.
 * No mock data fallbacks. Real backend parity only.
 */
export const apiClient = {
  // GET /health
  getHealth: async (): Promise<HealthStatusResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/health`, { method: "GET" });
    return await handleResponse<HealthStatusResponse>(res);
  },

  // GET /api/v1/market-data/status
  getMarketDataStatus: async (): Promise<MarketDataStatusResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/market-data/status`, { method: "GET" });
    return await handleResponse<MarketDataStatusResponse>(res);
  },

  // GET /api/v1/regime/market
  getMarketRegimeBtc: async (): Promise<MarketRegimeResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/regime/market`, { method: "GET" });
    return await handleResponse<MarketRegimeResponse>(res);
  },

  // GET /api/v1/regime/{symbol}
  getSymbolRegime: async (symbol: string): Promise<MarketRegimeResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/regime/${encodeURIComponent(symbol)}`, { method: "GET" });
    return await handleResponse<MarketRegimeResponse>(res);
  },

  // GET /api/v1/strategies/setups
  getStrategySetups: async (params?: {
    state?: string;
    eligible_only?: boolean;
    symbol?: string;
    limit?: number;
  }): Promise<StrategySetup[]> => {
    const baseUrl = getApiBaseUrl();
    const query = new URLSearchParams();
    if (params?.state && params.state !== "ALL") query.append("state", params.state);
    if (params?.eligible_only !== undefined) query.append("eligible_only", String(params.eligible_only));
    if (params?.symbol) query.append("symbol", params.symbol);
    if (params?.limit) query.append("limit", String(params.limit));

    const res = await fetch(`${baseUrl}/api/v1/strategies/setups?${query.toString()}`, { method: "GET" });
    return await handleResponse<StrategySetup[]>(res);
  },

  // GET /api/v1/strategies/setups/{setup_id}
  getStrategySetupDetail: async (setupId: string): Promise<StrategySetup> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/strategies/setups/${encodeURIComponent(setupId)}`, { method: "GET" });
    return await handleResponse<StrategySetup>(res);
  },

  // GET /api/v1/strategies/trend-pullback/{symbol}?refresh=...
  getLiveEvaluation: async (symbol: string, refresh = false): Promise<TrendPullbackEvaluation> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/strategies/trend-pullback/${encodeURIComponent(symbol)}?refresh=${refresh}`, { method: "GET" });
    return await handleResponse<TrendPullbackEvaluation>(res);
  },

  // GET /api/v1/strategies
  getStrategiesInfo: async (): Promise<StrategyInfo[]> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/strategies`, { method: "GET" });
    return await handleResponse<StrategyInfo[]>(res);
  },

  // GET /api/v1/market-data/symbols
  getSymbols: async (activeOnly = true, limit = 100): Promise<MarketSymbol[]> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/market-data/symbols?active_only=${activeOnly}&limit=${limit}`, { method: "GET" });
    return await handleResponse<MarketSymbol[]>(res);
  },

  // GET /api/v1/market-data/snapshot
  getSnapshot: async (symbol: string): Promise<MarketSnapshot> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/market-data/snapshot?symbol=${encodeURIComponent(symbol)}`, { method: "GET" });
    return await handleResponse<MarketSnapshot>(res);
  },

  // GET /api/v1/market-data/candles
  getCandles: async (symbol: string, timeframe: CandleTimeframe = "5m", limit = 200): Promise<Candle[]> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(
      `${baseUrl}/api/v1/market-data/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`,
      { method: "GET" }
    );
    const data = await handleResponse<any[]>(res);
    return normalizeCandles(data);
  },

  // GET /api/v1/settings
  getSettings: async (): Promise<RuntimeSettings> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/settings`, { method: "GET" });
    return await handleResponse<RuntimeSettings>(res);
  },

  // PATCH /api/v1/settings
  patchSettings: async (patch: RuntimeSettingsPatch): Promise<RuntimeSettings> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return await handleResponse<RuntimeSettings>(res);
  },

  // GET /api/v1/trades/active
  getActiveTrades: async (): Promise<ActiveTradesResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/trades/active`, { method: "GET" });
    return await handleResponse<ActiveTradesResponse>(res);
  },

  // GET /api/v1/trades/journal
  getTradeJournal: async (): Promise<TradeJournalResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/trades/journal`, { method: "GET" });
    return await handleResponse<TradeJournalResponse>(res);
  },

  // GET /api/v1/trades/telemetry
  getTradeTelemetry: async (): Promise<TelemetryFeedResponse> => {
    const baseUrl = getApiBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/trades/telemetry`, { method: "GET" });
    return await handleResponse<TelemetryFeedResponse>(res);
  },
};
