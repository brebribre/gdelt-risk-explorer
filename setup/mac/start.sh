#!/usr/bin/env bash
# Start the API (port 8787) and the web app (port 5173). Ctrl+C stops both.
#
# Usage:  setup/mac/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

[ -x "$ROOT/.venv/bin/python" ] || { echo "✗ Not set up yet. Run: setup/mac/setup.sh"; exit 1; }
[ -d "$ROOT/web/node_modules" ] || { echo "✗ Web dependencies missing. Run: setup/mac/setup.sh --skip-data"; exit 1; }
[ -f "$ROOT/data/gdelt.db" ] || { echo "✗ No data yet. Run: setup/mac/update-data.sh"; exit 1; }

"$ROOT/.venv/bin/python" "$ROOT/server/api.py" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

echo "App:     http://localhost:5173"
echo "Swagger: http://localhost:8787/api/docs"
echo "Press Ctrl+C to stop."
cd "$ROOT/web" && npm run dev
