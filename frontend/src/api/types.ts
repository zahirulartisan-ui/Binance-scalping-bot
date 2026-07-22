/**
 * Type definitions for Binance Scalping Bot Dashboard
 */

// Enums and Unions
export type AppEnvironment = "development" | "staging" | "production";

export type ComponentStatus = "ok" | "error" | "warning" | "unknown" | "ready" | "not_ready" | "enabled" | "disabled" | "active" | "inactive";

export type MarketRegimeType = 
  | "TRENDING_BULLISH"
  | "TRENDING_BEARISH"
  | "RANGING"
  | "HIGH_VOLATILITY"
  | "ABNORMAL_MARKET"
  | "NO_TRADE"
  | "INSUFFICIENT_DATA";

export type EntryPermissionType = 
  | "ALLOW_LONG"
  | "ALLOW_SHORT"
  | "ALLOW_BOTH"
  | "BLOCK_NEW_ENTRIES";

export type TrendDirectionType = "bullish" | "bearish" | "flat";

export type StrategySetupState = 
  | "NO_SETUP"
  | "FORMING"
  | "READY"
  | "INVALIDATED"
  | "EXPIRED"
  | "INSUFFICIENT_DATA"
  | "BLOCKED_BY_REGIME";

export type StrategyDirection = "LONG" | "SHORT" | "NONE";

export type CandleTimeframe = "1m" | "5m" | "15m";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type CycleStatus = "started" | "completed" | "partial_failure" | "failed" | "skipped";

// 1. Health Response
export interface HealthStatusResponse {
  application: { status: string; detail?: string };
  database: { status: string; detail?: string };
  environment: { status: AppEnvironment | string };
  demo_trading: { status: "enabled" | "disabled" | string };
  execution: { status: "enabled" | "disabled" | string };
  emergency_stop: { status: "active" | "inactive" | string };
  migrations: { status: "ready" | "not_ready" | "unknown" | string };
}

// 2. Market Data Status Response
export interface MarketDataStatusResponse {
  collection_enabled: boolean;
  runner_active: boolean;
  latest_cycle_status: CycleStatus | string | null;
  latest_cycle_started_at: string | null;
  latest_cycle_finished_at: string | null;
  latest_cycle_rejections: Record<string, string>;
}

// 3. Market Regime Response
export interface MarketRegimeResponse {
  symbol: string;
  evaluated_at: string;
  primary_regime: MarketRegimeType;
  entry_permission: EntryPermissionType;
  confidence_score: number; // 0 - 1
  trend_direction: TrendDirectionType;
  trend_strength_value: number;
  volatility_value: number;
  spread_value: number | null;
  data_fresh: boolean;
  btc_regime: string;
  market_wide_block: boolean;
  reasons: string[];
  safety_conditions: string[];
  indicator_snapshot: Record<string, any>;
}

// 4. Strategy Setup Item
export interface StrategySetup {
  setup_id: string;
  symbol: string;
  direction: StrategyDirection;
  setup_state: StrategySetupState;
  entry_zone_low: number;
  entry_zone_high: number;
  preferred_entry: number;
  stop_loss: number;
  take_profit: number;
  reward_to_risk: number;
  pullback_depth: number;
  volume_ratio: number;
  liquidity_sweep_detected: boolean;
  mss_detected: boolean; // Market Structure Shift
  eligible_for_signal: boolean;
  evaluated_at: string;
  expires_at: string;
}

// Live Trend Pullback Evaluation
export interface TrendPullbackEvaluation {
  setup_id?: string;
  symbol: string;
  evaluated_at: string;
  setup_state: StrategySetupState;
  direction: StrategyDirection;
  trend_summaries: {
    one_minute: { direction: string; strength: number; ema_aligned: boolean };
    five_minute: { direction: string; strength: number; ema_aligned: boolean };
    fifteen_minute: { direction: string; strength: number; ema_aligned: boolean };
  };
  ema_snapshot: {
    ema_9: number;
    ema_21: number;
    ema_50: number;
    ema_200: number;
    price: number;
  };
  pullback_detection: {
    in_pullback: boolean;
    pullback_depth: number;
    max_allowed_depth: number;
    touch_ema: string;
  };
  entry_zone: {
    low: number;
    high: number;
    preferred: number;
    zone_width_percent: number;
  };
  volume: {
    current_volume: number;
    avg_volume: number;
    volume_ratio: number;
    volume_surge: boolean;
  };
  rejection_confirmation: {
    confirmed: boolean;
    pattern_name: string;
    wick_ratio: number;
  };
  liquidity_sweep: {
    detected: boolean;
    level_swept: number;
    type: string;
  };
  market_structure_shift: {
    detected: boolean;
    break_level: number;
    timeframe: string;
  };
  risk: {
    stop_loss: number;
    take_profit: number;
    risk_amount: number;
    reward_amount: number;
    reward_to_risk: number;
  };
  reasons: string[];
  failed_conditions: string[];
  triggered_safety_conditions: string[];
  data_freshness: {
    is_fresh: boolean;
    age_seconds: number;
  };
}

// Strategy Info
export interface StrategyInfo {
  name: string;
  version: string;
  enabled: boolean;
  trading_mode: string;
  entry_timeframe: string;
  confirmation_timeframe: string;
  context_timeframe: string;
}

// 5. Symbol Item
export interface MarketSymbol {
  symbol: string;
  base_asset: string;
  quote_asset: string;
  trading_status: string;
  tick_size: number;
  step_size: number;
  minimum_quantity: number;
  minimum_notional: number;
  price_precision: number;
  quantity_precision: number;
  refreshed_at: string;
}

// 6. Market Snapshot
export interface MarketSnapshot {
  symbol: string;
  last_price: number;
  bid_price: number;
  ask_price: number;
  bid_quantity: number;
  ask_quantity: number;
  spread_bps: number;
  snapshot_at: string;
}

// 7. Candle Item
export interface Candle {
  symbol: string;
  timeframe: CandleTimeframe;
  open_time: string;
  close_time: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  volume: number;
  quote_volume: number;
  trade_count: number;
}

// 8. Runtime Settings
export interface RuntimeSettings {
  app_name: string;
  app_env: AppEnvironment | string;
  api_host: string;
  api_port: number;
  log_level: LogLevel;
  allowed_origins: string[];
  execution_enabled: boolean;
  demo_trading_mode: boolean;
  scanner_interval_seconds: number;
  risk_per_trade: number; // e.g. 0.01 (1%)
  maximum_open_trades: number;
  daily_loss_limit: number; // e.g. 0.05 (5%)
  emergency_stop: boolean;
}

// Runtime Settings Patch Request
export interface RuntimeSettingsPatch {
  log_level?: LogLevel;
  allowed_origins?: string[];
  execution_enabled?: boolean;
  demo_trading_mode?: boolean;
  scanner_interval_seconds?: number;
  risk_per_trade?: number;
  maximum_open_trades?: number;
  daily_loss_limit?: number;
  emergency_stop?: boolean;
}

// FastAPI Standard Error
export interface FastAPIError {
  detail: string | Array<{ loc: (string | number)[]; msg: string; type: string }>;
  status?: number;
}
