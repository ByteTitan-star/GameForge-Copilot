# GameForge Production Deployment Guide

> Zero-to-one guide for deploying GameForge on a fresh Linux server (Ubuntu 22.04+).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Server Setup](#2-server-setup)
3. [Clone the Repository](#3-clone-the-repository)
4. [Prepare Docker Files](#4-prepare-docker-files)
5. [Configure backend/.env](#5-configure-backendenv)
6. [Configure frontend/.env.production](#6-configure-frontendenvproduction)
7. [Build Images](#7-build-images)
8. [Database Migration](#8-database-migration)
9. [Start Services](#9-start-services)
10. [Verify Deployment](#10-verify-deployment)
11. [Maintenance](#11-maintenance)

---

## 1. Prerequisites

| Component  | Version     | Purpose                        |
|------------|-------------|--------------------------------|
| Docker     | 24+         | Container runtime              |
| Docker Compose | v2+     | Service orchestration          |
| Git        | 2.30+       | Source code                    |
| Domain/IP  | -           | Public access (e.g. 62.234.65.18) |

## 2. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker (official script)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin (if not bundled)
sudo apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

## 3. Clone the Repository

```bash
cd /opt
git clone <your-repo-url> GameForge-Copilot-main
cd GameForge-Copilot-main
```

## 4. Prepare Docker Files

The production deployment requires two additional files not in the default `docker/` folder:

### 4.1 Dockerfile.frontend

Create `docker/Dockerfile.frontend`:

```dockerfile
FROM node:22-slim AS build

WORKDIR /app

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN npm install -g pnpm@11.21.0 && pnpm config set registry https://registry.npmmirror.com && pnpm install --frozen-lockfile

COPY frontend ./
ENV VITE_API_BASE_URL=/agent/api/v1 VITE_HOSTING_BASE_URL=/agent
RUN pnpm run build

FROM nginx:1.27-alpine

COPY docker/nginx.frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
```

### 4.2 nginx.frontend.conf

Create `docker/nginx.frontend.conf`:

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 7200s;
        proxy_send_timeout 7200s;
    }

    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 7200s;
        proxy_send_timeout 7200s;
    }

    location ~ ^/(play|draft|preview)/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /healthz {
        proxy_pass http://backend:8000;
    }

    location = /agent { return 302 /agent/; }
    location /agent/ {
        rewrite ^/agent/$ /index.html last;
        rewrite ^/agent/(.*)$ /$1 last;
    }
    location = / { return 302 /agent/; }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 4.3 docker-compose.prod.yml

Create `docker-compose.prod.yml` at project root. This extends the base `docker-compose.yml` with the frontend service and production overrides:

```yaml
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: gameforge
      POSTGRES_PASSWORD: gameforge
      POSTGRES_DB: gameforge
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gameforge -d gameforge"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  rabbitmq:
    image: rabbitmq:3-management
    restart: unless-stopped
    environment:
      RABBITMQ_DEFAULT_USER: gameforge
      RABBITMQ_DEFAULT_PASS: gameforge
      RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS: "-rabbit consumer_timeout 7200000"
    ports:
      - "127.0.0.1:5672:5672"
      - "127.0.0.1:15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 5s
      timeout: 5s
      retries: 12

  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    user: "0:0"
    restart: unless-stopped
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://gameforge:gameforge@postgres:5432/gameforge
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://gameforge:gameforge@rabbitmq:5672/
      MESSAGING_BACKEND: rabbitmq
      HOSTING_ROOT: /data/hosting
    volumes:
      - hosting:/data/hosting
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    deploy:
      replicas: ${WORKER_REPLICAS:-1}
    user: "0:0"
    restart: unless-stopped
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://gameforge:gameforge@postgres:5432/gameforge
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://gameforge:gameforge@rabbitmq:5672/
      MESSAGING_BACKEND: rabbitmq
      HOSTING_ROOT: /data/hosting
    volumes:
      - hosting:/data/hosting
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }

  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  pgdata:
  redisdata:
  hosting:
```

## 5. Configure backend/.env

Create `/opt/GameForge-Copilot-main/backend/.env` with production values.

Below is a **diff summary** of what must change from the development defaults:

| Variable | Dev Value | Production Value | Notes |
|----------|-----------|-----------------|-------|
| `DATABASE_URL` | `...@localhost:5432/...` | `...@localhost:5432/...` | Overridden by compose `environment:` to use container hostname `postgres`. No change needed in .env. |
| `REDIS_URL` | `redis://localhost:6379/0` | Same | Overridden by compose. |
| `RABBITMQ_URL` | `amqp://...@localhost:5672/` | Same | Overridden by compose. |
| `FRONTEND_BASE_URL` | `http://127.0.0.1:5174` | `http://<YOUR_SERVER_IP>` | Must match the public URL users visit. |
| `HOSTING_BACKEND` | `s3` | `s3` (or `local`) | `s3` requires valid OSS credentials below. |
| `S3_AK` / `S3_SK` | - | Your Alibaba Cloud OSS keys | Required if `HOSTING_BACKEND=s3`. |
| `SANDBOX_BACKEND` | `daytona` | `daytona` | Requires valid `DAYTONA_API_KEY`. |
| `DAYTONA_API_KEY` | - | Your Daytona key | Required if sandbox=daytona. |
| `MAX_CONCURRENT_RUNS` | `3` | `1` | Reduce for resource-limited servers. |
| `MAX_CONCURRENT_TASKS` | `3` | `1` | Same. |
| `AUDIT_INTERVAL_MS` | `2500` | `500` | Tighter audit interval for production. |
| `AUDIT_MAX_BUFFER_CHARS` | `500` | `1500` | Larger buffer for production. |
| `ENV` | `development` | `production` | **Critical.** |
| `CORS_ORIGINS` | `http://127.0.0.1:5173,...` | `http://<YOUR_SERVER_IP>` | Only your public origin. |
| `DEV_ROUTES_ENABLED` | `true` | `false` | **Must disable in production.** |
| `API_PUBLIC_URL` | `http://127.0.0.1:8000` | `http://<YOUR_SERVER_IP>` | For OAuth callbacks. |
| `BUILD_PIPELINE_ENABLED` | `true` | `false` | Disable if not using build pipeline in prod. |
| `EMBEDDING_ENABLED` | `true` | `false` | Disable if not running TEI service. |
| `PINECONE_ENABLED` | `true` | `false` | Disable if not using vector search. |

### Template

```bash
cp backend/.env.example backend/.env
```

Then edit the values above. A minimal production `.env` is:

```ini
# === Core (overridden by compose for DB/Redis/RabbitMQ, but keep as fallback) ===
DATABASE_URL=postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://gameforge:gameforge@localhost:5672/
MESSAGING_BACKEND=rabbitmq

# === Security ===
JWT_SECRET=<GENERATE: openssl rand -base64 48>
JWT_ACCESS_TTL=7200
REFRESH_TTL=2592000
LLM_APIKEY_ENCRYPTION_KEY=<GENERATE: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# === Email ===
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=<your-email>
SMTP_PASS=<your-smtp-auth-code>
SMTP_FROM=<your-email>
SMTP_FROM_NAME=GameForge
ADMIN_CONTACT_EMAIL=<your-email>
FRONTEND_BASE_URL=http://<YOUR_SERVER_IP>

# === Object Storage (Alibaba Cloud OSS) ===
HOSTING_BACKEND=s3
HOSTING_ROOT=.hosting
S3_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
S3_REGION=oss-cn-beijing
S3_BUCKET=gameforge
S3_AK=<your-oss-access-key>
S3_SK=<your-oss-secret-key>
S3_PREFIX=gameforge
S3_ADDRESSING_STYLE=virtual

# === Sandbox ===
SANDBOX_BACKEND=daytona
SANDBOX_DAYTONA_ENABLED=true
SANDBOX_IMAGE=gameforge/sandbox
SANDBOX_DEFAULT_TIER=standard
DAYTONA_API_KEY=<your-daytona-key>
DAYTONA_TIMEOUT_S=300

# === Rate Limits ===
DEFAULT_DAILY_TOKEN_LIMIT=500000
DEFAULT_RATE_LIMIT_PER_MIN=30
MAX_CONCURRENT_RUNS=1
MAX_CONCURRENT_TASKS=1
MAX_VERSIONS_PER_GAME=20
MAX_DRAFTS_PER_USER=20
MAX_PUBLISHED_PER_USER=50
SYSTEM_DAILY_TOKEN_ALERT=5000000

# === Langfuse (optional) ===
LANGFUSE_SECRET_KEY=<your-langfuse-sk>
LANGFUSE_PUBLIC_KEY=<your-langfuse-pk>
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# === Streaming ===
STREAM_ENABLED=true
STREAM_BATCH_CHARS=4
STREAM_BATCH_MS=80

# === Content Audit ===
AUDIT_ENABLED=true
AUDIT_PROVIDER=openai_compat
AUDIT_MODEL=deepseek-v4-flash
AUDIT_APIKEY=<your-deepseek-key>
AUDIT_BASE_URL=https://api.deepseek.com
AUDIT_INTERVAL_MS=500
AUDIT_MIN_CHARS_BETWEEN=80
AUDIT_MAX_BUFFER_CHARS=1500
AUDIT_REQUEST_TIMEOUT=20
AUDIT_QUICK_FILTER=true

# === Environment ===
ENV=production
LOG_LEVEL=INFO
CORS_ORIGINS=http://<YOUR_SERVER_IP>

# === Code QA ===
CODE_QA_MAX_ATTEMPTS=3
THUMBNAIL_ENABLED=true

# === Embedding (disable if TEI not deployed) ===
EMBEDDING_ENABLED=false
EMBEDDING_PROVIDER=openai_compat
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_APIKEY=local
EMBEDDING_BASE_URL=http://127.0.0.1:8080/v1

# === Pinecone (disable if not needed) ===
PINECONE_ENABLED=false
PINECONE_API_KEY=<your-pinecone-key>
PINECONE_HOST=<your-pinecone-host>
PINECONE_INDEX=gameforge-semantic
PINECONE_NAMESPACE=default

# === Preference Extraction ===
PREFERENCE_EXTRACT_MODEL=deepseek-v4-flash
PREFERENCE_EXTRACT_APIKEY=<your-deepseek-key>
PREFERENCE_EXTRACT_BASE_URL=https://api.deepseek.com
SEMANTIC_CONFIRM_MODEL=deepseek-v4-flash
SEMANTIC_CONFIRM_APIKEY=<your-deepseek-key>
SEMANTIC_CONFIRM_BASE_URL=https://api.deepseek.com

# === Production Safety ===
DEV_ROUTES_ENABLED=false

# === OAuth (optional) ===
API_PUBLIC_URL=http://<YOUR_SERVER_IP>
OAUTH_GITHUB_CLIENT_ID=
OAUTH_GITHUB_CLIENT_SECRET=
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=

# === Build Pipeline (disable if not used) ===
BUILD_PIPELINE_ENABLED=false
BUILDER_BACKEND=docker
BUILDER_IMAGE=gameforge-builder:v1
PNPM_STORE_PATH=.pnpm-store
NPM_REGISTRY=https://registry.npmmirror.com
BUILD_MAX_RETRIES=3
BUILDER_TIMEOUT_S=300

# === LLM Timeout ===
LLM_REQUEST_TIMEOUT=600
RUNNING_STALE_TIMEOUT_S=7200
LLM_CODE_MAX_TOKENS=32768
LLM_CONTINUATION_MAX_ROUNDS=3
LLM_CONTINUATION_TAIL_CHARS=8000
```

## 6. Configure frontend/.env.production

This file is **only needed for local `pnpm build`**. When using `docker-compose.prod.yml`, the Dockerfile.frontend hardcodes the VITE env vars at build time via `ENV` directive, so you can skip this file.

If you do need it (e.g. for a standalone frontend build):

```bash
cat > frontend/.env.production << 'EOF'
VITE_API_BASE_URL=http://<YOUR_SERVER_IP>/api/v1
VITE_HOSTING_BASE_URL=http://<YOUR_SERVER_IP>
VITE_WS_BASE_URL=ws://<YOUR_SERVER_IP>
EOF
```

> **Note**: The production Dockerfile.frontend uses relative paths (`/agent/api/v1`) which work behind nginx reverse proxy. The `.env.production` with absolute URLs is only for non-Docker builds.

## 7. Build Images

```bash
cd /opt/GameForge-Copilot-main

# Build all services
docker compose -f docker-compose.prod.yml build

# This builds: backend, worker, frontend
# Postgres, Redis, RabbitMQ use official images (pulled automatically).
```

## 8. Database Migration

```bash
# Start only the database first
docker compose -f docker-compose.prod.yml up -d postgres
sleep 5

# Run Alembic migrations inside the backend container
docker compose -f docker-compose.prod.yml run --rm backend \
  uv run alembic upgrade head
```

## 9. Start Services

```bash
# Start everything
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

## 10. Verify Deployment

```bash
# Health check
curl http://localhost/healthz

# API check
curl http://localhost/api/v1/health

# Frontend — open in browser
# http://<YOUR_SERVER_IP>/agent/
```

Expected results:

- `GET /healthz` returns 200
- Frontend loads at `http://<YOUR_SERVER_IP>/agent/`
- WebSocket connects at `ws://<YOUR_SERVER_IP>/ws/`

## 11. Maintenance

### Update deployment

```bash
cd /opt/GameForge-Copilot-main
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### Edit config and restart

```bash
# Edit backend config
nano /opt/GameForge-Copilot-main/backend/.env

# Restart backend + worker (no rebuild needed for env changes)
docker compose -f docker-compose.prod.yml restart backend worker
```

### Edit frontend config and rebuild

```bash
# Frontend env vars are baked at build time, so a rebuild is required
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Scale workers

```bash
docker compose -f docker-compose.prod.yml up -d --scale worker=2
```

### View logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
```

### Backup database

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U gameforge gameforge > backup_$(date +%Y%m%d).sql
```

---

## File Locations on Server

| File | Path |
|------|------|
| Backend config | `/opt/GameForge-Copilot-main/backend/.env` |
| Frontend config | Baked at build time in Dockerfile.frontend |
| Docker Compose | `/opt/GameForge-Copilot-main/docker-compose.prod.yml` |
| Nginx config | `/opt/GameForge-Copilot-main/docker/nginx.frontend.conf` |
| DB data volume | Docker volume `pgdata` |
| Redis data volume | Docker volume `redisdata` |
| Hosting volume | Docker volume `hosting` |
