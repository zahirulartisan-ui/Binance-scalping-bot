# Binance Scalping Bot

Batch 1 establishes the project foundation for a Binance scalping auto-trading V1 application. It does not include Binance API integration, scanner logic, strategies, risk engines, orders, positions, mock trading data, or fabricated account metrics.

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
| `BACKEND_EXECUTION_ENABLED` | Must default to `false`. |
| `FRONTEND_API_BASE_URL` | Browser-facing backend base URL. |

Backend `.env.example`:

| Name | Purpose |
| --- | --- |
| `APP_NAME` | API display name. |
| `APP_ENV` | Runtime environment label. |
| `LOG_LEVEL` | Structured logging level. |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL. |
| `EXECUTION_ENABLED` | Live execution guard, default `false`. |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins. |

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

## Remaining Batch 2 Scope

- Define trading-domain models and persistence tables only after V1 behavior is specified.
- Add Binance API client integration behind explicit configuration and tests.
- Add scanner, signal, risk, order, position, and journal behavior in scoped batches.
- Add execution enablement controls with strong safety checks.
- Add real data ingestion and observability without mock balances, fake signals, or fabricated performance.
