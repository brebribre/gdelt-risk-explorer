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

-----------------------

# GDELT Risk Explorer

This is a prototype for finding recent supply-chain risk news. It turns GDELT’s periodically published Global Knowledge Graph (GKG) data into a searchable local database, then presents the results through a filterable web interface with a timeline, article list, and map.

The main pieces are `the README`, the Python ingestion pipeline in `ingest.py`, the risk taxonomy in `taxonomy.py`, the API in `api.py`, and the React application under `web/src`.

## How the pieces fit together

```text
GDELT 15-minute data feeds
          │
          ▼
ingest/ingest.py ── maps GDELT themes to project risk types
          │
          ▼
data/gdelt.db (SQLite + full-text search)
          │
          ▼
server/api.py (read-only JSON API, port 8787)
          │
          ▼
web/ React + Vite UI (port 5173)
          ├── filters and article list
          ├── hourly timeline
          └── Leaflet map
```

The database is generated locally and excluded from version control. The project intentionally keeps its backend lightweight: the ingestion script and API use Python’s standard library; the frontend uses React, TypeScript, Vite, and Leaflet.

## 1. Turning GDELT data into risk articles

`ingest.py` downloads GDELT GKG batches, extracts the relevant article metadata, and stores articles that match the project’s risk taxonomy.

### Feed selection and incremental fetching

GDELT publishes timestamped batches every 15 minutes. The script supports two feeds:

- `en`: the English GKG feed.
- `translated`: the translated feed, which can include articles originally published in other languages.

By default it covers 48 hours from the latest published batch, which is 192 15-minute intervals per feed. It fetches batches concurrently, with eight workers by default. A missing batch is treated as a normal possibility; other failures are retried, then reported.

The script records batch status in SQLite. Successful batches are skipped on later runs, so re-running is incremental. Articles are also deduplicated by URL.

### Parsing and selecting articles

The ingestion code reads each ZIP archive in memory; it does not save the raw downloads. It parses GKG’s tab-separated rows using known column positions, then:

1. **Looks for risk themes.** It maps a row’s GDELT themes to project risk codes. Rows with no matching risk theme are discarded.
2. **Extracts places and organizations.** It records location names and coordinates, organization names, selected numeric counts, source, page title, language, and GDELT tone.
3. **Chooses one primary location.** It compares the text offsets of locations with the offsets of risk themes. Nearby locations score better, while country and regional locations receive penalties so that more specific places tend to win.
4. **Chooses a timestamp.** It uses a page’s precise publication timestamp when available and plausible; otherwise it uses the GDELT-seen time. It retains both times so the UI can distinguish publication from discovery.
5. **Stores supporting metadata.** It keeps the recognized GDELT themes and the project risk codes, as well as the other locations mentioned in the article.

Country names are resolved using `fips_countries.tsv`. Those are GDELT’s FIPS 10-4 country codes, not ISO country codes.

### Risk taxonomy

`taxonomy.py` is the central mapping between GDELT’s theme labels and the app’s risk categories. It defines categories such as natural hazards, industrial incidents, labour and unrest, logistics, geopolitical and trade, financial, cyber, ESG and human rights, and health.

Each risk type has a stable code, a display label, and one or more GDELT themes. For example, several flood-related themes map to the project’s `flood` risk type. The same taxonomy is used during ingestion to classify articles and by the API to supply category and risk labels to the UI.

### SQLite database

The schema is created by the ingestion script in `data/gdelt.db`. Its main tables are:

- `article`: one row per stored article, including timestamps, feed, title, source, tone, selected location, and JSON-encoded lists of places, organizations, counts, themes, and risks.
- `article_risk`: one row for each risk assigned to an article, with its category. This supports risk filtering and counts.
- `article_country`: countries mentioned in each article. This enables the “any country mentioned” filter, separate from filtering by the primary event location.
- `article_fts`: an SQLite FTS5 full-text index over titles, organizations, places, and sources. Its Porter tokenizer supports English stemming.
- `batch`: which GDELT feed batches were scanned and whether they were successfully processed or missing.

Indexes on timestamps, risks, categories, and countries help the API filter the database efficiently.

## 2. Read-only JSON API

`api.py` runs a small threaded HTTP server on `127.0.0.1:8787`. It opens the SQLite database in read-only mode and exposes two endpoints:

- `GET /api/meta` returns totals, date range, feed and batch statistics, and the risk taxonomy.
- `GET /api/search` returns matching articles, the total match count, timeline buckets, map points, and filter facets.

### Search and filters

The search endpoint accepts query parameters for:

- Text search across headline, organizations, places, and source.
- Risk types and categories.
- Countries, either by primary event location or by any country mentioned.
- Language and feed.
- Publication time range, tone threshold, source substring, and exact place.
- Precise-location-only filtering, sorting, limit, and offset.

The search input supports several forms:

- `port strike`: all terms must match; the FTS tokenizer can match English inflections.
- `"quoted text"`: phrase search.
- `port*`: prefix search.

Search terms are converted into an FTS5 query, and filter values are passed as SQL parameters. The API caps a page at 200 articles; the UI requests 50 at a time.

### Results beyond the article list

A search response includes more than the current page of articles:

- **Timeline:** article counts by ingestion hour. It deliberately ignores the selected time range so users can see the wider ingestion window while selecting a time interval.
- **Map points:** articles grouped by their chosen primary location, with count and a flag indicating whether the location is city-level.
- **Facets:** counts for risks, countries, languages, and sources, allowing users to see available alternatives while filtering.

The API’s `meta` endpoint reports the time GDELT saw an article separately from the article’s publication time. That distinction matters because some pages are discovered late and may have old publication dates.

## 3. React interface

The frontend is a React 18 and TypeScript app configured by `package.json` and `vite.config.ts`. During development, Vite serves the UI on port 5173 and proxies `/api` requests to the Python server on port 8787.

`main.tsx` loads the CSS, Leaflet styles, and root `App`. The app’s main state and data flow are in `App.tsx`.

### App state and navigation

`App` owns the selected filters, search results, loaded article pages, errors, and current display mode. It:

- Loads metadata from `/api/meta`.
- Debounces text search input by 300 ms.
- Converts filters into `/api/search` parameters and fetches results.
- Aborts a previous request when a newer search starts.
- Adds later article pages when the user selects “Load more.”
- Keeps filters in the URL query string so a search can be shared or revisited.
- Shows active filters as removable chips.

The shared types, filter defaults, URL conversion, API parameter construction, language names, and formatting utilities live in `lib.ts`.

### UI components

- `Sidebar.tsx` provides filters for time, risk category and type, country, feed/language, tone, location precision, and source. Risk choices come from the API’s taxonomy; counts come from the current facets.
- `Timeline.tsx` shows hourly article counts. Dragging across bars selects a time range.
- `MapView.tsx` renders grouped locations as Leaflet circles. Larger counts produce larger markers; clicking a marker filters the results to that place. It zooms to a small set of results and otherwise shows a world view.
- `ArticleCard.tsx` displays risk labels, headline link, source, relative time, language, tone, location, organizations, and selected reported counts. Its expanded view includes more places, GDELT themes, and timestamp/feed details.
- `styles.css` defines the two-column sidebar/main layout, responsive wrapping in the top bar, cards, timeline, and map presentation.

The main display can be switched between split list-and-map, list-only, and map-only views.

## Running it

The documented local workflow is:

```bash
python3 ingest/ingest.py --hours 48
python3 server/api.py
cd web
npm install
npm run dev
```

Then open `http://localhost:5173`. The ingestion step creates the database; the API serves it; and the Vite app provides the browser interface.

## Important limitations

The project is an exploratory prototype, and its results should be treated as signals rather than verified incident reports:

- GDELT’s theme tagging is keyword-based and can be noisy.
- The event location is a heuristic based on proximity to a risk-related text offset, not a confirmed incident location.
- Some articles have old publication dates despite being newly discovered by GDELT.
- Headlines link to publisher pages; the article body is not downloaded or stored.
- Translated-feed articles retain their original-language headlines, even though some extracted places and organizations are in English.
- Country identifiers use FIPS 10-4 codes.

In short: the project is a local ETL-plus-search application. Its main design choice is to do the expensive collection and normalization once into SQLite, then serve fast, read-only, filterable views of that curated dataset.