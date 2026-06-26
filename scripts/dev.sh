#!/usr/bin/env bash
# Run the full NetGuard stack locally without Docker, then open the dashboard.
#
#   ./scripts/dev.sh        # then open http://localhost:3000  (Ctrl-C to stop)
#
# Requires on PATH: python3, redis-server/redis-cli, node/npm.
# Set GROQ_API_KEY in your environment first if you want AIOps diagnosis to work.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REDIS_PORT=6390
PIDS=()

cleanup() {
  kill "${PIDS[@]}" 2>/dev/null || true
  for p in 3000 8001 8002 8003 8004; do fuser -k "${p}/tcp" 2>/dev/null || true; done
  redis-cli -p "$REDIS_PORT" shutdown nosave 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Create a per-service venv on first run, then echo its bin dir.
venv_bin() {
  local svc="$1" d="$ROOT/services/$1/.venv"
  if [ ! -x "$d/bin/uvicorn" ]; then
    python3 -m venv "$d"
    "$d/bin/pip" -q install -r "$ROOT/services/$svc/requirements.txt"
  fi
  echo "$d/bin"
}

redis-server --port "$REDIS_PORT" --save '' --appendonly no --daemonize yes
echo "redis: $(redis-cli -p "$REDIS_PORT" ping)"

INF=$(venv_bin inference); AIO=$(venv_bin aiops-engine)
COL=$(venv_bin collector); API=$(venv_bin backend-api)

INFERENCE_MODEL_DIR="$ROOT/model/artifacts" \
  "$INF/uvicorn" app.main:app --app-dir "$ROOT/services/inference" --port 8001 & PIDS+=($!)
GROQ_API_KEY="${GROQ_API_KEY:-}" \
  "$AIO/uvicorn" app.main:app --app-dir "$ROOT/services/aiops-engine" --port 8004 & PIDS+=($!)
COLLECTOR_INFERENCE_URL=http://127.0.0.1:8001 COLLECTOR_REDIS_URL="redis://127.0.0.1:$REDIS_PORT/0" \
  "$COL/uvicorn" app.main:app --app-dir "$ROOT/services/collector" --port 8002 & PIDS+=($!)
API_REDIS_URL="redis://127.0.0.1:$REDIS_PORT/0" API_INFERENCE_URL=http://127.0.0.1:8001 API_AIOPS_URL=http://127.0.0.1:8004 \
  "$API/uvicorn" app.main:app --app-dir "$ROOT/services/backend-api" --port 8003 & PIDS+=($!)

( cd "$ROOT/frontend" && npm install --no-audit --no-fund >/dev/null 2>&1 && npm run dev -- --port 3000 ) & PIDS+=($!)

echo ""
echo "NetGuard is starting → http://localhost:3000   (Ctrl-C to stop everything)"
wait
