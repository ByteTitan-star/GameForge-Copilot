#!/usr/bin/env bash
# PostgreSQL 全量备份（docs/09 MVP）
set -euo pipefail

: "${DATABASE_URL:?Set DATABASE_URL, e.g. postgresql://user:pass@localhost:5432/gameforge}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${1:-./backups/gameforge_${STAMP}.sql.gz}"

mkdir -p "$(dirname "$OUT")"
pg_dump "$DATABASE_URL" | gzip > "$OUT"
echo "Backup written to $OUT"
