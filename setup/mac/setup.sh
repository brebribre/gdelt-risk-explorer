#!/usr/bin/env bash
# One-time setup for macOS (also works on Linux):
# Python virtualenv + API dependencies, web dependencies, first data download.
#
# Usage:  setup/mac/setup.sh [--hours N] [--skip-data]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOURS=48
SKIP_DATA=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hours) HOURS="$2"; shift 2 ;;
    --skip-data) SKIP_DATA=1; shift ;;
    *) echo "Unknown option: $1"; echo "Usage: setup/mac/setup.sh [--hours N] [--skip-data]"; exit 1 ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "✗ '$1' not found. $2"; exit 1; }
}
need python3 "Install Python 3.10+ from https://www.python.org/downloads/ (or: brew install python)"
need node "Install Node.js 18+ from https://nodejs.org/ (or: brew install node)"
need npm "npm is installed together with Node.js"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "✗ Python 3.10+ required (found $(python3 -V))"; exit 1; }
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' \
  || { echo "✗ Node.js 18+ required (found $(node -v))"; exit 1; }

echo "→ Python virtualenv + API dependencies"
[ -d "$ROOT/.venv" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -q --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -q -r "$ROOT/server/requirements.txt"

echo "→ Web dependencies"
(cd "$ROOT/web" && npm install --no-audit --no-fund)

if [ "$SKIP_DATA" = 1 ]; then
  echo "→ Skipping data download"
else
  echo "→ Downloading the last ${HOURS}h of GDELT data (about 1.35 GB per day; takes a few minutes)"
  "$ROOT/.venv/bin/python" "$ROOT/ingest/ingest.py" --hours "$HOURS"
fi

echo
echo "✓ Setup done. Start the app with: setup/mac/start.sh"
