# Binance Scalping Bot

Batch 1 established the project foundation for a Binance scalping auto-trading V1 application. Batch 2 added central settings, database session handling, schema foundations, settings APIs, and expanded health reporting. Batch 3 added Binance public market-data integration. Batch 4 adds a deterministic market regime filter. It does not include scanner ranking, coin selection, trading strategies, risk calculation, account access, order execution, mock trading data, or fabricated account metrics.

## Completed Batch 1 Scope

- Monorepo layout with `backend/` and `frontend/`.
- FastAPI backend using synchronous SQLAlchemy 2.0, Alembic, Pydantic Settings, PostgreSQL, pytest, Ruff, and mypy.
- One consolidated settings class in `backend/app/core/settings.py`.
- One SQLAlchemy declarative base in `backend/app/database/base.py`.
- Standard synchronous session factory in `backend/app/database/session.py`.
- `/health` endpoint reporting application, database, and execution status.
- Execution defaults to disabled.
- UTC timestamps in structured JSON logging.
- Backend folders for API, core, database, models, schemas, services, and tests.
- Initial Alembic setup with one empty foundation migration.
- React TypeScript Vite frontend with ESLint and a minimal trading-terminal shell.
- Sidebar and top status bar with placeholder pages for Dashboard, Scanner, Signals, Active Trades, Journal, Risk, and Settings.
- Frontend integrates only with backend health status.
- UI clearly displays `Demo Trading` and `Execution Disabled`.
- Docker Compose for backend, frontend, and PostgreSQL.
- GitHub Actions CI for backend tests, lint, type-check, Alembic head check, frontend lint, and frontend production build.

## Batch 2 Scope

- Central Pydantic Settings class for development, test, and production environments.
- Validated settings for API host/port, log level, PostgreSQL URL, CORS, Binance Demo credential placeholders, execution safety, demo mode, scanner interval, risk per trade, max open trades, daily loss limit, and emergency stop.
- Secret values are read from environment variables only and are redacted from serialization.
- Production startup validation rejects unsafe V1 configurations.
- Synchronous SQLAlchemy 2.0 engine/session factory with commit, rollback, and close handling.
- Startup database connectivity verification with fail-closed execution behavior.
- Initial production-structured database models and migration for application settings, scanner audit data, signal/order/fill/position/risk/journal/system-event records.
- Public authenticated-ready settings endpoints: `GET /api/v1/settings` and `PATCH /api/v1/settings`.
- Expanded `/health` response for app, database, environment, demo trading, execution, emergency stop, and migration readiness.

## Batch 3 Scope

- Public Binance market-data client for exchange info, book ticker, recent price, and `1m`/`5m` klines.
- Bounded timeout, retry, and exponential backoff handling for public REST calls.
- Active USDT spot symbol metadata refresh with inactive, suspended, leveraged-token, non-spot, and invalid symbol rejection.
- Closed-candle validation and idempotent OHLCV persistence.
- Live market snapshot validation and persistence with spread basis points.
- Lifecycle-safe background market-data runner, disabled by default, with overlap prevention and graceful shutdown.
- Market-data read endpoints with safe parameter validation and explicit empty states.
- Migration `202607210003` for Batch 3 market-data tables.

## Batch 4 Scope

- Deterministic market regime classification from persisted market-data candles and snapshots.
- Supported regimes: `TRENDING_BULLISH`, `TRENDING_BEARISH`, `RANGING`, `HIGH_VOLATILITY`, `ABNORMAL_MARKET`, `NO_TRADE`, and `INSUFFICIENT_DATA`.
- Entry permissions: `ALLOW_LONG`, `ALLOW_SHORT`, `ALLOW_BOTH`, and `BLOCK_NEW_ENTRIES`.
- BTCUSDT market-wide filter before individual symbol permissions.
- Latest per-symbol regime snapshot persistence via migration `202607210004`.
- Read-only endpoints: `GET /api/v1/regime/market` and `GET /api/v1/regime/{symbol}`.
- Scanner integration hook through `MarketRegimeService.annotate_scanner_candidates`. A full scanner workflow is not present in this repository yet, so no scanner ranking or coin selection was added.

## Architecture

```text
.
|-- backend
|   |-- alembic
|   |-- app
|   |   |-- api
|   |   |-- core
|   |   |-- database
|   |   |-- models
|   |   |-- schemas
|   |   `-- services
|   `-- tests
|-- frontend
|   `-- src
|-- .github/workflows
`-- docker-compose.yml
```

The backend is the API and persistence boundary. The frontend is a read-only Batch 1 shell that displays health status only. PostgreSQL is the configured database target for local and containerized runs.

## Environment Variables

Root `.env.example`:

| Name | Purpose |
| --- | --- |
| `POSTGRES_DB` | Local Docker PostgreSQL database name. |
| `POSTGRES_USER` | Local Docker PostgreSQL username. |
| `POSTGRES_PASSWORD` | Local Docker PostgreSQL password placeholder. |
| `BACKEND_DATABASE_URL` | Backend database URL for Docker Compose. |
| `BACKEND_APP_ENV` | Backend environment: `development`, `test`, or `production`. |
| `BACKEND_EXECUTION_ENABLED` | Must default to `false`. |
| `BACKEND_DEMO_TRADING_MODE` | Demo trading mode flag, default `true`. |
| `BACKEND_EMERGENCY_STOP` | Emergency stop flag, default `false`. |
| `BACKEND_MARKET_DATA_COLLECTION_ENABLED` | Background market-data collection flag, default `false`. |
| `FRONTEND_API_BASE_URL` | Browser-facing backend base URL. |

Backend `.env.example`:

| Name | Purpose |
| --- | --- |
| `APP_NAME` | API display name. |
| `APP_ENV` | Runtime environment: `development`, `test`, or `production`. |
| `API_HOST` | API bind host. |
| `API_PORT` | API bind port. |
| `LOG_LEVEL` | Structured logging level. |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL. |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins. |
| `BINANCE_DEMO_API_KEY` | Binance Demo API key from environment only. |
| `BINANCE_DEMO_API_SECRET` | Binance Demo API secret from environment only. |
| `EXECUTION_ENABLED` | Live execution guard, default `false`. |
| `DEMO_TRADING_MODE` | Demo trading mode flag, default `true`. |
| `SCANNER_INTERVAL_SECONDS` | Scanner interval setting placeholder. No scanner logic exists yet. |
| `RISK_PER_TRADE` | Risk per trade setting placeholder. No risk engine exists yet. |
| `MAXIMUM_OPEN_TRADES` | Maximum open trades setting placeholder. |
| `DAILY_LOSS_LIMIT` | Daily loss limit setting placeholder. |
| `EMERGENCY_STOP` | Emergency stop flag. If active, execution fails closed. |
| `BINANCE_MARKET_DATA_BASE_URL` | Public Binance REST base URL. |
| `BINANCE_MARKET_DATA_TIMEOUT_SECONDS` | Public market-data HTTP timeout. |
| `BINANCE_MARKET_DATA_MAX_RETRIES` | Bounded retry count. |
| `BINANCE_MARKET_DATA_BACKOFF_SECONDS` | Base exponential backoff delay. |
| `MARKET_DATA_COLLECTION_ENABLED` | Background collection flag, default `false`. |
| `MARKET_DATA_SYMBOL_REFRESH_SECONDS` | Symbol metadata refresh cadence. |
| `MARKET_DATA_CYCLE_INTERVAL_SECONDS` | Market-data runner cycle interval. |
| `MARKET_DATA_SYMBOLS` | Comma-separated USDT symbols for collection. |
| `REGIME_MINIMUM_CANDLES` | Minimum candle history required before classification. |
| `REGIME_TREND_STRENGTH_THRESHOLD` | Minimum trend-strength proxy for trending regimes. |
| `REGIME_ATR_PERCENT_MIN` | Reserved lower ATR percent bound. |
| `REGIME_ATR_PERCENT_MAX` | Maximum ATR percent before high-volatility blocking. |
| `REGIME_REALIZED_VOLATILITY_MAX` | Maximum realized volatility percent. |
| `REGIME_ABNORMAL_CANDLE_PERCENT` | Single-candle displacement threshold for abnormal markets. |
| `REGIME_VOLUME_SPIKE_MULTIPLIER` | Volume spike threshold versus rolling average. |
| `REGIME_MAX_SPREAD_BPS` | Maximum safe spread in basis points. |
| `REGIME_EMA_SLOPE_THRESHOLD` | Minimum EMA slope threshold for trend direction. |
| `REGIME_RANGE_COMPRESSION_THRESHOLD` | Recent range threshold for ranging classification. |
| `REGIME_BTC_BLOCK_VOLATILITY_PERCENT` | BTC volatility safety threshold. |
| `REGIME_CACHE_SECONDS` | Short TTL for repeated regime calculations. |

Frontend `.env.example`:

| Name | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Backend API base URL for `/health`. |

## Local Setup

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker Compose:

```bash
docker compose up --build
```

Services:

- Backend API: `http://localhost:8000`
- Health endpoint: `http://localhost:8000/health`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`

## Verification Commands

Backend:

```bash
cd backend
pytest
ruff check .
mypy .
alembic heads
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Docker Compose:

```bash
docker compose config
```

## Database Tables

| Table | Purpose |
| --- | --- |
| `app_settings` | Persist allowlisted runtime settings only. |
| `scanner_runs` | Store future scanner run audit envelopes, without scanner logic. |
| `scanner_decisions` | Store future per-symbol scanner decisions, without generated decisions. |
| `signals` | Store future signal records, without strategy generation. |
| `risk_decisions` | Store future risk decision audit records, without risk engine logic. |
| `orders` | Store future order lifecycle records, without placing or simulating orders. |
| `fills` | Store future exchange fill records, without mock fills. |
| `positions` | Store future position state records, without fabricated positions. |
| `position_events` | Store future position event audit records. |
| `trade_journal_entries` | Store future journal notes and reviews. |
| `system_events` | Store system-level audit events. |
| `exchange_symbols` | Store active Binance USDT spot symbol metadata. |
| `ohlcv_candles` | Store validated closed `1m` and `5m` OHLCV candles. |
| `market_snapshots` | Store current public price/book snapshots and spread bps. |
| `market_data_cycles` | Store market-data runner cycle status, counts, duration, and rejections. |
| `market_regime_snapshots` | Store latest deterministic regime result per symbol. |

## Market Data Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/market-data/status` | Return collection flag, runner activity, and latest cycle status. |
| `GET /api/v1/market-data/symbols` | Return persisted eligible symbol metadata. |
| `GET /api/v1/market-data/candles` | Return persisted candles by symbol/timeframe/date range/limit. |
| `GET /api/v1/market-data/snapshot` | Return the latest persisted snapshot for a symbol, or `null`. |

## Market Regime Decision Flow

1. Validate the symbol and require persisted active symbol metadata.
2. Load closed `1m` candles and the latest snapshot.
3. Evaluate BTCUSDT first for stale data, spread, abnormal candles, volatility, and trend conflict.
4. Calculate EMA 20, EMA 50, optional EMA 200, ATR percent, realized volatility, trend-strength proxy, recent range, volume ratio, displacement, and spread.
5. Block abnormal, stale, extreme-spread, high-volatility, and insufficient-data conditions before allowing any directional regime.
6. Classify bullish or bearish trends only when EMA stack, slope, price location, trend strength, and volatility agree.
7. Return ranging/no-trade when evidence is weak or conflicting.

`ABNORMAL_MARKET`, `HIGH_VOLATILITY`, `NO_TRADE`, and `INSUFFICIENT_DATA` always return `BLOCK_NEW_ENTRIES`. BTC market-wide blocks also force `BLOCK_NEW_ENTRIES`.

## Batch 1 Verification Results

Executed locally on Windows from branch `codex/batch-1-project-foundation`.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && .\.venv\Scripts\python.exe -m pytest` | Passed: `1 passed, 1 warning` |
| Backend lint | `cd backend && .\.venv\Scripts\python.exe -m ruff check .` | Passed: `All checks passed!` |
| Backend type-check | `cd backend && .\.venv\Scripts\python.exe -m mypy .` | Passed: `Success: no issues found in 20 source files` |
| Alembic heads | `cd backend && .\.venv\Scripts\alembic.exe heads` | Passed: exactly one head, `202607210001 (head)` |
| Frontend lint | `cd frontend && npm.cmd run lint` | Passed |
| Frontend production build | `cd frontend && npm.cmd run build` | Passed: Vite built `29 modules` in `963ms` |
| Docker Compose YAML structure | `.\backend\.venv\Scripts\python.exe -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('docker-compose.yml').read_text()); assert {'postgres','backend','frontend'} <= set(data['services']); print('docker-compose.yml YAML valid with services:', ', '.join(data['services']))"` | Passed: `docker-compose.yml YAML valid with services: postgres, backend, frontend` |
| Docker Compose config | `docker compose config` | Not completed locally: Docker CLI is not installed or not available on PATH in this environment. |

The only local verification gap is Docker CLI availability. The compose file was still parsed as YAML and confirmed to include the required `postgres`, `backend`, and `frontend` services.

## Batch 2 Verification Results

Executed locally on Windows from branch `codex/batch-2-database-settings`.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && .\.venv\Scripts\python.exe -m pytest` | Passed: `10 passed, 14 warnings` |
| Backend lint | `cd backend && .\.venv\Scripts\python.exe -m ruff check .` | Passed after import formatting fix |
| Backend type-check | `cd backend && .\.venv\Scripts\python.exe -m mypy .` | Passed: `Success: no issues found in 31 source files` |
| Alembic upgrade/downgrade/upgrade | `cd backend && APP_ENV=test DATABASE_URL=sqlite+pysqlite:///./.pytest-local/alembic-verify.db alembic upgrade head && alembic downgrade 202607210001 && alembic upgrade head` | Passed locally against isolated test DB |
| Alembic heads | `cd backend && .\.venv\Scripts\alembic.exe heads` | Passed: exactly one head, `202607210002 (head)` |
| Schema and indexes | SQLAlchemy inspector against `.pytest-local/alembic-verify.db` | Passed: all 11 Batch 2 tables and expected indexes present |
| Frontend lint | `cd frontend && npm.cmd run lint` | Passed |
| Frontend production build | `cd frontend && npm.cmd run build` | Passed: Vite built `29 modules` |
| Docker Compose YAML structure | Python YAML parser | Passed: required `postgres`, `backend`, and `frontend` services present |
| Docker Compose config | `docker compose config` | Not completed locally: Docker CLI is not installed or not available on PATH in this environment. |

The only local verification gap is Docker CLI availability. No Batch 2 code failure is known from the available local checks.

## Batch 3 Verification Results

Executed locally on Windows from branch `codex/batch-3-market-data`.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && .\.venv\Scripts\python.exe -m pytest` | Passed: `28 passed, 36 warnings` |
| Backend lint | `cd backend && .\.venv\Scripts\python.exe -m ruff check .` | Passed: `All checks passed!` |
| Backend type-check | `cd backend && .\.venv\Scripts\python.exe -m mypy .` | Passed: `Success: no issues found in 43 source files` |
| Alembic upgrade/downgrade/upgrade | `APP_ENV=test DATABASE_URL=sqlite+pysqlite:///./.pytest-local/alembic-batch3.db alembic upgrade head && alembic downgrade 202607210002 && alembic upgrade head` | Passed |
| Alembic heads | `cd backend && .\.venv\Scripts\alembic.exe heads` | Passed: exactly one head, `202607210003 (head)` |
| Schema and indexes | SQLAlchemy inspector against `.pytest-local/alembic-batch3.db` | Passed: Batch 3 tables and expected indexes present |
| Frontend lint | `cd frontend && npm.cmd run lint` | Passed |
| Frontend production build | `cd frontend && npm.cmd run build` | Passed: Vite built `29 modules` |
| Docker Compose YAML structure | Python YAML parser | Passed: required `postgres`, `backend`, and `frontend` services present |
| Docker Compose config | `docker compose config` | Not completed locally: Docker CLI is not installed or not available on PATH in this environment. |

The only local verification gap is Docker CLI availability.

## Batch 4 Verification Results

Executed locally on Windows from branch `codex/batch-4-market-regime`.

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && .\.venv\Scripts\python.exe -m pytest` | Passed: `33 passed, 40 warnings` |
| Backend lint | `cd backend && .\.venv\Scripts\python.exe -m ruff check .` | Passed: `All checks passed!` |
| Backend type-check | `cd backend && .\.venv\Scripts\python.exe -m mypy .` | Passed: `Success: no issues found in 51 source files` |
| Alembic upgrade/downgrade/upgrade | `APP_ENV=test DATABASE_URL=sqlite+pysqlite:///./.pytest-local/alembic-regime.db alembic upgrade head && alembic downgrade 202607210003 && alembic upgrade head` | Passed |
| Alembic heads | `cd backend && .\.venv\Scripts\alembic.exe heads` | Passed: exactly one head, `202607210004 (head)` |
| Schema and indexes | SQLAlchemy inspector against `.pytest-local/alembic-regime.db` | Passed: `market_regime_snapshots` and `ix_regime_snapshots_symbol_evaluated_at` present |
| Frontend lint | `cd frontend && npm.cmd run lint` | Passed |
| Frontend production build | `cd frontend && npm.cmd run build` | Passed: Vite built `29 modules` |
| Docker Compose YAML structure | Python YAML parser | Passed: required `postgres`, `backend`, and `frontend` services present |
| Docker Compose config | `docker compose config` | Not completed locally: Docker CLI is not installed or not available on PATH in this environment. |

The only local verification gap is Docker CLI availability. Existing scanner workflow integration is limited to a service hook because the repository does not yet contain a scanner implementation.

## Remaining Batch 5 Scope

Coin Scanner and Candidate Ranking only.
