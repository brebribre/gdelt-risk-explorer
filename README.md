# GDELT Risk Explorer (prototype)

Search and filter supply-chain risk news from the last 48 hours of GDELT 2.0 GKG data
(English + machine-translated feeds).

```
setup/     install / start / update scripts for macOS and Windows
ingest/    Python: downloads GDELT raw 15-min GKG files, keeps risk articles, writes SQLite
  taxonomy.py         our risk types and which GDELT themes map to them
  ingest.py           the downloader / parser
server/    Python: FastAPI read-only JSON API over the database (port 8787, Swagger at /api/docs)
web/       React + Vite + Leaflet UI (port 5173, proxies /api to 8787)
data/      gdelt.db (created by ingest)
```

Needs Python 3.10+ and Node.js 18+.

## Quick start

| | macOS | Windows |
|---|---|---|
| Install + download data (once) | `setup/mac/setup.sh` | double-click `setup\windows\setup.bat` |
| Start the app | `setup/mac/start.sh` | double-click `setup\windows\start.bat` |
| Refresh data | `setup/mac/update-data.sh` | double-click `setup\windows\update-data.bat` |

See [setup/README.md](setup/README.md) for options and troubleshooting.

## Run manually

Ingestion uses only the Python standard library. The API needs FastAPI + Uvicorn
(`server/requirements.txt`).

```bash
# 1. Fetch data (incremental: re-running only downloads new batches)
python3 ingest/ingest.py --hours 48

# 2. API (first time: create the virtualenv)
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
.venv/bin/python server/api.py

# 3. UI (in another terminal)
cd web && npm install && npm run dev
```

Open http://localhost:5173.

## API

Interactive docs (Swagger UI): http://localhost:8787/api/docs
OpenAPI spec: http://localhost:8787/api/openapi.json

| Endpoint | Purpose |
|---|---|
| `GET /api/search` | Search and filter articles; returns results, hourly timeline, map points and facet counts |
| `GET /api/articles/{id}` | One article |
| `GET /api/meta` | Dataset overview (counts, time range) and the risk taxonomy |

## Search

- Words must all match, with English stemming: `port strike` also finds "strikes".
- `"quoted text"` searches a phrase, `port*` is a prefix search.
- Searches headline, organisations, places and source domain.
- Translated articles keep their original-language headline; organisations and places are in English.

## Known limitations

- GDELT theme tagging is keyword-based and noisy (e.g. history articles tagged as fire/flood).
- "Event location" is a heuristic: the place mentioned closest to the risk keyword.
- Country codes are FIPS 10-4 (GDELT's), not ISO.
- Some articles carry very old publish dates (pages GDELT only just discovered); they are marked "old article".
- Headlines link to publishers; no article text is stored.

Data source: The GDELT Project (gdeltproject.org).
