# GDELT Risk Explorer (prototype)

Search and filter supply-chain risk news from the last 48 hours of GDELT 2.0 GKG data
(English + machine-translated feeds).

```
ingest/    Python: downloads GDELT raw 15-min GKG files, keeps risk articles, writes SQLite
  taxonomy.py         our risk types and which GDELT themes map to them
  ingest.py           the downloader / parser
server/    Python: small read-only JSON API over the database (port 8787)
web/       React + Vite + Leaflet UI (port 5173, proxies /api to 8787)
data/      gdelt.db (created by ingest)
```

No Python packages needed (standard library only). Node 18+ for the web app.

## Run

```bash
# 1. Fetch data (incremental: re-running only downloads new batches)
python3 ingest/ingest.py --hours 48

# 2. API
python3 server/api.py

# 3. UI (in another terminal)
cd web && npm install && npm run dev
```

Open http://localhost:5173.

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
