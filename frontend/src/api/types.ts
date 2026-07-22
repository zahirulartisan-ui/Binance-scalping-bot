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
  demo_account_balance?: number;
  scanner_interval_seconds: number;
  signal_execution_automation_enabled?: boolean;
  signal_execution_batch_size?: number;
  risk_per_trade: number; // e.g. 0.01 (1%)
  maximum_open_trades: number;
  daily_loss_limit: number; // e.g. 0.05 (5%)
  emergency_stop: boolean;
  position_monitoring_enabled?: boolean;
  position_monitoring_interval_seconds?: number;
  position_monitoring_price_max_age_seconds?: number;
}

// Runtime Settings Patch Request
export interface RuntimeSettingsPatch {
  log_level?: LogLevel;
  allowed_origins?: string[];
  execution_enabled?: boolean;
  demo_trading_mode?: boolean;
  demo_account_balance?: number;
  scanner_interval_seconds?: number;
  signal_execution_automation_enabled?: boolean;
  signal_execution_batch_size?: number;
  risk_per_trade?: number;
  maximum_open_trades?: number;
  daily_loss_limit?: number;
  emergency_stop?: boolean;
  position_monitoring_enabled?: boolean;
  position_monitoring_interval_seconds?: number;
  position_monitoring_price_max_age_seconds?: number;
}

export interface TradesSummary {
  total_positions: number;
  total_orders: number;
  total_open_quantity: number;
  total_unrealized_pnl: number;
  total_realized_pnl: number;
  last_synced_at: string | null;
}

export interface ActiveTradePosition {
  id: string;
  symbol: string;
  direction: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number;
  opened_at: string;
  status: string;
}

export interface ActiveTradeOrder {
  id: string;
  symbol: string;
  direction: string;
  type: string;
  price: number | null;
  quantity: number;
  filled_quantity: number;
  fee: number;
  created_at: string;
  status: string;
  mode: string;
}

export interface ActiveTradesResponse {
  summary: TradesSummary;
  positions: ActiveTradePosition[];
  orders: ActiveTradeOrder[];
}

export interface TradeJournalEntry {
  entry_id: string;
  entry_type: string;
  title: string;
  body: string;
  entry_at: string;
  metadata_json: Record<string, any>;
}

export interface TradeJournalItem {
  id: string;
  symbol: string | null;
  strategy: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward: string;
  pnl: number;
  result: string;
  opened_at: string | null;
  closed_at: string | null;
  duration_minutes: number | null;
  signal_grade: string | null;
  setup_id: string | null;
  exit_reason: string | null;
  mode: string;
  journal_entries: TradeJournalEntry[];
}

export interface TradeJournalSummary {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_pnl: number;
  average_pnl: number;
}

export interface TradeJournalResponse {
  summary: TradeJournalSummary;
  trades: TradeJournalItem[];
}

export interface TelemetryEvent {
  event_id: string;
  level: string;
  source: string;
  message: string;
  event_at: string;
  metadata_json: Record<string, any>;
}

export interface TelemetryFeedResponse {
  summary: TradesSummary;
  recent_system_events: TelemetryEvent[];
  recent_trade_notes: TradeJournalEntry[];
  recent_closed_trades: TradeJournalItem[];
  active_positions: ActiveTradePosition[];
  pending_orders: ActiveTradeOrder[];
}

// FastAPI Standard Error
export interface FastAPIError {
  detail: string | Array<{ loc: (string | number)[]; msg: string; type: string }>;
  status?: number;
}
