#!/usr/bin/env bash
# 预下载 BAAI/bge-small-zh-v1.5 到 data/embedding-models（供 docker compose embedding 挂载）。
# 默认走 ModelScope（国内可达）；HF 镜像常因 etag 失败。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/data/embedding-models/BAAI/bge-small-zh-v1.5"
MARKER="$DEST/model.safetensors"

if [[ -f "$MARKER" ]]; then
  echo "[download] already present: $DEST"
  exit 0
fi

mkdir -p "$(dirname "$DEST")"
echo "[download] ModelScope -> $DEST"

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  UV_BIN="uv"
fi

cd "$ROOT/backend"
GF_DEST="$DEST" "$UV_BIN" run --with modelscope python -c "
import os
from modelscope.hub.snapshot_download import snapshot_download
dest = os.environ['GF_DEST']
path = snapshot_download('BAAI/bge-small-zh-v1.5', local_dir=dest)
print(f'[download] ok: {path}')
"
