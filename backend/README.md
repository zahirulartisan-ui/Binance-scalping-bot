# Backend

FastAPI backend for the Binance Scalping Bot.

## Batch 3 Market Data

Batch 3 adds Binance public market-data integration only. It does not access account balances, place or simulate orders, rank coins, grade signals, calculate risk, or enable trading execution.

### Environment

| Variable | Purpose |
| --- | --- |
| `BINANCE_MARKET_DATA_BASE_URL` | Public Binance REST base URL. Default `https://api.binance.com`. |
| `BINANCE_MARKET_DATA_TIMEOUT_SECONDS` | HTTP timeout for public market-data requests. |
| `BINANCE_MARKET_DATA_MAX_RETRIES` | Bounded retry count for timeout, rate-limit, and server errors. |
| `BINANCE_MARKET_DATA_BACKOFF_SECONDS` | Base exponential backoff delay. |
| `MARKET_DATA_COLLECTION_ENABLED` | Enables background market-data collection when true. Default false. |
| `MARKET_DATA_SYMBOL_REFRESH_SECONDS` | Symbol metadata refresh cadence. |
| `MARKET_DATA_CYCLE_INTERVAL_SECONDS` | Runner cycle interval. |
| `MARKET_DATA_SYMBOLS` | Comma-separated active USDT symbols for collection. |

### Endpoints

- `GET /api/v1/market-data/status`
- `GET /api/v1/market-data/symbols`
- `GET /api/v1/market-data/candles`
- `GET /api/v1/market-data/snapshot`

All endpoints return persisted data only. Empty states are explicit, and no mock market data is returned.

### Tables

- `exchange_symbols`: active Binance USDT spot symbol metadata for future validation.
- `ohlcv_candles`: closed 1m and 5m OHLCV candles, unique by symbol/timeframe/open time.
- `market_snapshots`: last price and book ticker snapshots with spread basis points.
- `market_data_cycles`: background runner cycle status, duration, counts, and rejection reasons.

### Verification

```bash
pytest
ruff check .
mypy .
alembic upgrade head
alembic downgrade 202607210002
alembic upgrade head
alembic heads
```

## Batch 4 Market Regime Filter

Batch 4 adds deterministic regime classification from persisted market-data records. It does not execute trades and does not implement scanner ranking, signal grading, risk, order execution, or position management.

### Regimes and Permissions

Regimes:

- `TRENDING_BULLISH`
- `TRENDING_BEARISH`
- `RANGING`
- `HIGH_VOLATILITY`
- `ABNORMAL_MARKET`
- `NO_TRADE`
- `INSUFFICIENT_DATA`

Entry permissions:

- `ALLOW_LONG`
- `ALLOW_SHORT`
- `ALLOW_BOTH`
- `BLOCK_NEW_ENTRIES`

Unsafe regimes and BTC market-wide blocks always return `BLOCK_NEW_ENTRIES`.

### Regime Endpoints

- `GET /api/v1/regime/market`
- `GET /api/v1/regime/{symbol}`

### Regime Configuration

Settings live in the existing central Pydantic settings class:

- `REGIME_MINIMUM_CANDLES`
- `REGIME_TREND_STRENGTH_THRESHOLD`
- `REGIME_ATR_PERCENT_MIN`
- `REGIME_ATR_PERCENT_MAX`
- `REGIME_REALIZED_VOLATILITY_MAX`
- `REGIME_ABNORMAL_CANDLE_PERCENT`
- `REGIME_VOLUME_SPIKE_MULTIPLIER`
- `REGIME_MAX_SPREAD_BPS`
- `REGIME_EMA_SLOPE_THRESHOLD`
- `REGIME_RANGE_COMPRESSION_THRESHOLD`
- `REGIME_BTC_BLOCK_VOLATILITY_PERCENT`
- `REGIME_CACHE_SECONDS`

### Persistence

`market_regime_snapshots` stores the latest regime result per symbol with evaluated timestamp, regime, entry permission, reasons, safety conditions, BTC regime, market-wide block flag, and indicator snapshot.
