# Local Development

[Chinese product README](../README_zh.md)

This guide contains the detailed setup, configuration, verification, and troubleshooting information kept out of the product-facing README.

## Prerequisites

Install the following before the first run:

- Docker Desktop with Docker Compose
- Node.js 20+ and pnpm 9+
- [uv](https://docs.astral.sh/uv/)

`uv` resolves the backend's Python 3.12 runtime from `backend/.python-version` when needed.

## Local Configuration

Create untracked local configuration files from the examples:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

The default values are suitable for local Docker-backed dependencies. Do not commit `.env` files or put API keys in documentation, screenshots, or screen recordings.

### Important Variables

| File | Variable | Local default | Purpose |
| --- | --- | --- | --- |
| `backend/.env` | `DATABASE_URL` | `postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge` | PostgreSQL connection |
| `backend/.env` | `REDIS_URL` | `redis://localhost:6379/0` | cache and generation checkpoints |
| `backend/.env` | `RABBITMQ_URL` | `amqp://gameforge:gameforge@localhost:5672/` | Worker queue and real-time events |
| `backend/.env` | `CORS_ORIGINS` | `http://127.0.0.1:5173,...` | browser origins allowed by the API |
| `backend/.env` | `SANDBOX_BACKEND` | `local` | local development build backend; use `docker` only after building the sandbox image |
| `backend/.env` | `THUMBNAIL_ENABLED` | `true` | after a successful Playwright QA pass, optionally capture a game-card cover |
| `backend/.env` | `CODE_QA_MAX_ATTEMPTS` | `3` | CodeQaLoop attempts (generate + repair), including the first generate |
| `frontend/.env` | `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | REST API base URL |
| `frontend/.env` | `VITE_HOSTING_BASE_URL` | optional | hosting root for `/play` and `/draft` pages |
| `frontend/.env` | `VITE_WS_BASE_URL` | optional | WebSocket root; inferred when omitted |

For the complete list, read the commented `backend/.env.example` and `frontend/.env.example` files.

## First Run

From the repository root, start the three required infrastructure services:

```bash
docker compose up -d postgres redis rabbitmq
docker compose ps
```

Then initialize backend dependencies, the database schema, and bundled official games:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_official_games
```

Run the seed command again after editing an official-game source asset. It is safe to run more than once.

## Running the Application

The API, Worker, and frontend run as separate local processes. Start each from a separate terminal.

```bash
# API
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Worker
cd backend
uv run python -m app.messaging.worker
```

```bash
# Frontend
cd frontend
pnpm install
pnpm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The Worker is required for email verification and game-generation runs. With the default development email configuration, the verification code appears in the Worker terminal instead of being delivered by SMTP.

## Health Checks

Use these endpoints after starting every service:

| Check | URL | Expected result |
| --- | --- | --- |
| API liveness | [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz) | healthy API response |
| Dependency readiness | [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) | PostgreSQL, Redis, and RabbitMQ are ready |
| API contract | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | interactive OpenAPI documentation |
| Official sample game | [http://127.0.0.1:8000/play/official-neon-snake](http://127.0.0.1:8000/play/official-neon-snake) | playable HTML response |

## Tests and Builds

Run tests from their owning application directories:

```bash
# Backend tests
cd backend
uv run pytest -q
```

```bash
# Frontend unit tests
cd frontend
pnpm test

# Type-check and production build
pnpm run build
```

The optional real-service smoke check requires the API and local dependencies to be running:

```bash
cd frontend
pnpm smoke:real
```

## Docker Backend Mode

For a Dockerized API and Worker, first build the sandbox image, then start the services:

```bash
docker compose --profile build-sandbox build sandbox
docker compose up -d postgres redis rabbitmq backend worker
```

Apply migrations and seed official games inside the backend container on a fresh environment:

```bash
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m scripts.seed_official_games
```

The frontend is normally run locally with `pnpm run dev` during development.

## Required Browser Playtest (CodeQaLoop)

Generation Workers **must** run real Chromium playtests. Static DOM checks are diagnostics only and cannot mark QA as passed. Without Playwright/Chromium, CodeQaLoop records `failure_kind=infra` and cannot reach `done`.

Install Playwright + Chromium on every Worker host:

```bash
cd backend
uv sync --extra playwright
uv run playwright install chromium
```

Windows PowerShell:

```powershell
cd backend
uv sync --extra playwright
uv run playwright install chromium
uv run python -m app.messaging.worker
```

Linux containers should bake browser dependencies into the Worker image (`docker/Dockerfile.worker` installs Chromium via `playwright install --with-deps`). Screenshot failures only affect covers (`THUMBNAIL_ENABLED`); missing Chromium blocks QA pass.

## Windows Troubleshooting

| Symptom | Check and fix |
| --- | --- |
| `uv` or `pnpm` is not found | Install the required tool, open a new terminal, and run the command again. |
| Frontend cannot start on port 5173 | Stop the process using 5173 or intentionally change the Vite port and update `CORS_ORIGINS` and `FRONTEND_BASE_URL` to match. |
| Browser requests fail or authentication seems unresponsive | Use one host consistently: `127.0.0.1` or `localhost`. The default configuration uses `127.0.0.1`. Restart the API after changing CORS settings. |
| `/ready` reports an unavailable dependency | Start Docker Desktop, run `docker compose ps`, and verify PostgreSQL, Redis, and RabbitMQ are healthy. |
| No verification code or a Forge run remains queued | Ensure the Worker terminal is running and connected to RabbitMQ. |
| Forge generation fails before it begins | Verify the account email, then save and test a working LLM provider configuration in Settings. |
| A game card has no screenshot cover | Expected unless the Worker has Playwright + Chromium and `THUMBNAIL_ENABLED=true`. Missing Chromium also blocks CodeQaLoop from passing. |
| A local environment has stale schema | Run `cd backend` followed by `uv run alembic upgrade head`. |

## Ports

| Service | Address |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| API | `http://127.0.0.1:8000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ management | `http://127.0.0.1:15672` |

## Related Project Documentation

- [OpenAPI contract](../contracts/openapi.json)
- [API integration notes](../contracts/INTEGRATION.md)
- [API changelog](../contracts/CHANGELOG.md)
