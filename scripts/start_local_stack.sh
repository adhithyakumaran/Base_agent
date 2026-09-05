#!/usr/bin/env bash
# Start QA orchestrator + console for local testing
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export QA_RUNNER="${QA_RUNNER:-playwright}"
export LLM_ENABLED="${LLM_ENABLED:-true}"
export PYTHONPATH="$ROOT/src:$ROOT"

echo "Starting QA orchestrator on :43124 (QA_RUNNER=$QA_RUNNER)..."
python3 scripts/local_agent_server.py --host 127.0.0.1 --port 43124 &
ORCH_PID=$!

sleep 2
echo "Starting QA console on :43123..."
cd qa-console
LOCAL_AGENT_URL=http://127.0.0.1:43124 npm run dev &
UI_PID=$!

trap 'kill $ORCH_PID $UI_PID 2>/dev/null || true' EXIT
echo ""
echo "  Console:  http://127.0.0.1:43123"
echo "  Agent API: http://127.0.0.1:43124/health"
echo ""
wait
