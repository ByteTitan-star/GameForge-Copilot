# Quick Start: Production Docker Deployment

> Assumes Docker & Docker Compose v2 are already installed on the server.

## 1. Enter Project Directory

```bash
cd /opt/GameForge-Copilot-main
```

## 2. Verify Config Files Exist

```bash
ls -la backend/.env frontend/.env.production
```

- `backend/.env` — backend, database, Redis, RabbitMQ, etc.
- `frontend/.env.production` — frontend build-time variables (VITE_*)

## 3. Review / Edit Config (if needed)

```bash
# Backend config
nano /opt/GameForge-Copilot-main/backend/.env

# Frontend config
nano /opt/GameForge-Copilot-main/frontend/.env.production
```

## 4. Start All Services

```bash
cd /opt/GameForge-Copilot-main
docker compose --env-file backend/.env up -d
```

This starts: postgres, redis, rabbitmq, backend, worker, frontend (and any other services defined in `docker-compose.yml`).

## 5. After Editing Backend Config — Restart Services

```bash
cd /opt/GameForge-Copilot-main
docker compose --env-file backend/.env up -d
```

## 6. After Editing Frontend Config — Rebuild Frontend

Frontend env vars (`VITE_*`) are baked at build time, so a rebuild is required:

```bash
docker compose --env-file backend/.env build frontend
docker compose --env-file backend/.env up -d frontend
```

## 7. Check Service Status

```bash
docker compose ps
docker compose logs -f --tail=100
```
