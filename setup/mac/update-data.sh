#!/usr/bin/env bash
# Fetch new GDELT batches into data/gdelt.db. Incremental: only downloads batches not stored yet.
# The API can keep running while this runs.
#
# Usage:  setup/mac/update-data.sh [--hours N]     (default 48)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -x "$ROOT/.venv/bin/python" ] || { echo "✗ Not set up yet. Run: setup/mac/setup.sh"; exit 1; }

"$ROOT/.venv/bin/python" "$ROOT/ingest/ingest.py" "$@"
