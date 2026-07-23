# Binance Scalping Bot

A FastAPI, PostgreSQL, and React trading-system project being migrated to a strict **Binance USD-M Futures Demo-only** architecture.

## Safety boundary

This repository is constrained to:

- Binance USD-M Futures Demo only
- USDT perpetual contracts only
- Future LONG and SHORT support
- Backend-controlled execution
- Execution disabled by default
- Emergency-stop fail-closed behavior

This repository does **not** support:

- Binance Spot order execution
- Binance production Futures execution
- Real-money trading
- Production Binance credentials
- Arbitrary exchange hosts
- Fake Binance order IDs, fills, positions, balances, or PnL

The only allowlisted exchange host for Prompt 1 is:

```text
https://demo-fapi.binance.com
```

Any Spot, production, HTTP, malformed, empty, or arbitrary trading endpoint must be rejected by the application safety layer.

## Current implementation status

The repository already contains:

- FastAPI backend
- PostgreSQL and SQLAlchemy persistence
- Alembic migrations
- React and TypeScript frontend
- Public market-data collection
- Market-regime evaluation
- Trend Pullback strategy evaluation
- Signal, order, position, risk, journal, and telemetry models
- Health and readiness APIs
- Ruff, mypy, pytest, frontend lint, and frontend build CI configuration

Prompt 1 is the **Futures Demo safety-foundation phase**. It does not complete authenticated account synchronization or real Binance Futures Demo order execution.

Still out of scope for Prompt 1:

- Futures account and available-margin synchronization
- Position-mode, leverage, and margin-mode synchronization
- LONG and SHORT order submission
- Exchange-side stop-loss and take-profit orders
- Position management and reconciliation
- Scanner-to-execution automation

Do not claim Binance Futures Demo execution is complete until those later phases are implemented and verified.

## Health and readiness

`GET /health` reports:

- application status
- database readiness
- migration readiness
- exchange scope
- USD-M Futures product type
- Futures Demo environment
- configured trading and market-data endpoints
- endpoint allowlist status
- credential readiness
- execution state
- emergency-stop state
- execution readiness
- machine-readable blocking reason codes

Expected blocking reason codes include:

- `execution_disabled`
- `emergency_stop_active`
- `futures_demo_credentials_missing`
- `unsafe_exchange_endpoint`
- `unsupported_trading_mode`
- `database_not_ready`
- `migrations_not_ready`

Read-only startup is permitted without Binance credentials while execution is disabled. Execution readiness must remain blocked until every safety gate passes.

## Environment configuration

Copy the example files before local use:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Never commit real credentials.

### Required safety defaults

```env
EXECUTION_ENABLED=false
DEMO_TRADING_MODE=true
EMERGENCY_STOP=false
BINANCE_TRADING_BASE_URL=https://demo-fapi.binance.com
BINANCE_MARKET_DATA_BASE_URL=https://demo-fapi.binance.com
BINANCE_DEMO_API_KEY=
BINANCE_DEMO_API_SECRET=
```

The empty credential values allow read-only startup. They do not make execution ready.

### Root Docker environment

The root `.env.example` uses the corresponding `BACKEND_` variables:

```env
BACKEND_EXECUTION_ENABLED=false
BACKEND_DEMO_TRADING_MODE=true
BACKEND_EMERGENCY_STOP=false
BACKEND_BINANCE_TRADING_BASE_URL=https://demo-fapi.binance.com
BACKEND_BINANCE_MARKET_DATA_BASE_URL=https://demo-fapi.binance.com
BACKEND_BINANCE_DEMO_API_KEY=
BACKEND_BINANCE_DEMO_API_SECRET=
```

Do not replace these values with `api.binance.com`, `fapi.binance.com`, a Spot endpoint, an HTTP URL, or a custom host.

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### Docker Compose

```bash
docker compose up --build
```

Services:

- Backend API: `http://localhost:8000`
- Health endpoint: `http://localhost:8000/health`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`

## Deployment constraints

Deployment must preserve the same safety boundary:

- execution remains disabled by default
- only Binance Futures Demo credentials may be configured
- only the allowlisted HTTPS Demo endpoint may be used
- production Binance endpoints are prohibited
- Spot endpoints are prohibited
- missing database or migration readiness blocks execution
- emergency stop overrides all execution settings

The application may run as a read-only service before account synchronization and order execution are implemented.

## Verification

Backend:

```bash
cd backend
ruff check .
mypy .
pytest
alembic heads
alembic upgrade head
python -m compileall app tests
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Repository safety checks:

```bash
git grep -n "api.binance.com\|fapi.binance.com"
git grep -n "EXECUTION_ENABLED=true"
git grep -n "BINANCE_API_KEY\|BINANCE_API_SECRET"
```

Any production trading URL, generic production credential field, active Spot execution path, or fake Binance exchange record must be treated as a release blocker.

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

The backend is the API, safety, exchange-integration, and persistence boundary. The frontend must display backend-derived status and must not fabricate account or trading data.
