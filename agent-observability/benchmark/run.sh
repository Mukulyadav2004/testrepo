#!/usr/bin/env bash
# Convenience wrapper: validates dependencies, sets default env vars if absent,
# then runs the benchmark suite.
#
# Usage (from repo root):
#   bash benchmark/run.sh
#
# Override any default:
#   GRPC_HOST=10.0.0.1 API_BASE_URL=http://10.0.0.1:8000 bash benchmark/run.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── dependency check ───────────────────────────────────────────────────────────
echo "Checking Python dependencies…"
python3 -c "import grpc, asyncpg, redis, httpx" 2>/dev/null || {
  echo ""
  echo "Missing dependencies. Install with:"
  echo "  pip install grpcio asyncpg redis httpx"
  exit 1
}
echo "All dependencies found."

# ── defaults (can be overridden by the caller's environment) ──────────────────
export GRPC_HOST="${GRPC_HOST:-localhost}"
export GRPC_PORT="${GRPC_PORT:-50051}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export DATABASE_URL="${DATABASE_URL:-postgresql://agentobs:agentobs@localhost:5432/agentobs}"
export API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo ""
echo "Connection targets:"
echo "  gRPC        → ${GRPC_HOST}:${GRPC_PORT}"
echo "  Redis       → ${REDIS_HOST}:${REDIS_PORT}"
echo "  PostgreSQL  → ${DATABASE_URL}"
echo "  REST API    → ${API_BASE_URL}"
echo ""

python3 "${SCRIPT_DIR}/load_test.py"
