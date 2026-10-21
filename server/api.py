"""Read-only JSON API over the SQLite database built by ingest/ingest.py.

    .venv/bin/python server/api.py        # serves on http://localhost:8787

Swagger UI:   http://localhost:8787/api/docs
OpenAPI spec: http://localhost:8787/api/openapi.json
"""

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingest"))
from taxonomy import as_json  # noqa: E402

DB_PATH = ROOT / "data" / "gdelt.db"
PORT = 8787
MAX_LIMIT = 200
MAP_POINTS = 1500


# ---------------------------------------------------------------------------
# Response models (these drive the Swagger schemas)
# ---------------------------------------------------------------------------

class Location(BaseModel):
    name: str = Field(description="Place name as GDELT resolved it", examples=["Bekasi, Jawa Barat, Indonesia"])
    type: int = Field(description="1 country, 2 US state, 3 US city, 4 world city, 5 world region (ADM1)")
    cc: str = Field(description="FIPS 10-4 country code (GDELT's codes, not ISO)", examples=["ID"])
    country: str = Field(examples=["Indonesia"])
    lat: float
    lon: float


class ReportedCount(BaseModel):
    type: str = Field(description="GDELT count type: KILL, WOUND, AFFECT, ARREST, KIDNAP, PROTEST, SEIZE, …")
    n: int
    object: str = Field(description="What was counted, e.g. 'workers' (may be empty)")


class Article(BaseModel):
    id: int
    t: str = Field(description="Publish time (UTC). Page timestamp when available, else GDELT batch time")
    seen: str = Field(description="When GDELT saw the article (15-minute batch time, UTC)")
    pubExact: bool = Field(description="True if `t` is the page's own publish timestamp")
    feed: Literal["en", "translated"]
    src: str = Field(description="Source domain", examples=["reuters.com"])
    url: str
    title: str = Field(description="Headline in the original language")
    lang: str = Field(description="ISO 639 source language code", examples=["eng", "ind"])
    tone: float = Field(description="GDELT document tone, −100…+100 (usually −10…+10)")
    loc: Optional[Location] = Field(description="Best-guess event location: place mentioned closest to the risk keyword")
    places: list[str] = Field(description="All places mentioned, in order of first mention (max 8)")
    orgs: list[str] = Field(description="Organisations mentioned (max 10)")
    counts: list[ReportedCount]
    risks: list[str] = Field(description="Our risk-type codes (see /api/meta)", examples=[["fire", "industrial_accident"]])
    themes: list[str] = Field(description="The GDELT GKG themes that produced the risk types")


class TimelineBucket(BaseModel):
    hour: str = Field(description="UTC hour, YYYY-MM-DDTHH", examples=["2026-10-20T14"])
    n: int


class MapPoint(BaseModel):
    name: str
    country: Optional[str]
    lat: float
    lon: float
    n: int = Field(description="Number of matching articles at this location")
    precise: int = Field(description="1 if city-level, 0 if country/region centroid")


class RiskFacet(BaseModel):
    code: str
    n: int


class CountryFacet(BaseModel):
    cc: str
    name: Optional[str]
    n: int


class LangFacet(BaseModel):
    code: str
    n: int


class SourceFacet(BaseModel):
    src: str
    n: int


class Facets(BaseModel):
    risks: list[RiskFacet] = Field(description="Counts per risk type (ignores the risk filters)")
    countries: list[CountryFacet] = Field(description="Counts per event-location country (ignores the country filter), top 60")
    langs: list[LangFacet] = Field(description="Counts per language (ignores the language filter), top 40")
    sources: list[SourceFacet] = Field(description="Top 15 source domains")


class SearchResponse(BaseModel):
    total: int = Field(description="Number of articles matching all filters")
    limit: int
    offset: int
    items: list[Article]
    timeline: list[TimelineBucket] = Field(description="Articles per hour over the ingestion window (ignores from/to)")
    points: list[MapPoint] = Field(description=f"Up to {MAP_POINTS} event locations, most articles first")
    facets: Facets


class Category(BaseModel):
    code: str
    label: str


class RiskType(BaseModel):
    code: str
    category: str
    label: str
    gdeltThemes: list[str] = Field(description="GDELT GKG themes mapped to this risk type")


class Meta(BaseModel):
    total: int = Field(description="Risk articles in the database")
    from_: str = Field(alias="from", description="Earliest batch time (UTC)")
    to: str = Field(description="Latest batch time (UTC)")
    feeds: dict[str, int] = Field(description="Articles per feed")
    batches: dict[str, int] = Field(description="GDELT batches by status (ok / missing)")
    scanned: int = Field(description="GDELT articles scanned before filtering")
    categories: list[Category]
    riskTypes: list[RiskType]


# ---------------------------------------------------------------------------
# Query logic
# ---------------------------------------------------------------------------

def connect():
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def fts_query(text):
    """Turn user input into a safe FTS5 query. All words must match (stemmed, so strike = strikes);
    "quoted text" is a phrase, a trailing * makes a prefix search (port* = port, ports, Portugal)."""
    parts = []
    for phrase, word in re.findall(r'"([^"]+)"|(\S+)', text):
        if phrase:
            parts.append('"' + phrase.replace('"', "") + '"')
        else:
            prefix = word.endswith("*")
            w = re.sub(r"[^\w\-.&']", "", word)
            if w:
                parts.append('"' + w + '"' + ("*" if prefix else ""))
    return " ".join(parts)


def split_csv(value):
    return [v for v in (value or "").split(",") if v]


def build_where(f, exclude=()):
    """WHERE clause for the filters in `f`. `exclude` skips filters (used for facet counts and the timeline)."""
    where, args = [], []

    def any_in(sql, values):
        where.append(sql.format(",".join("?" * len(values))))
        args.extend(values)

    if "q" not in exclude and f["q"] and fts_query(f["q"]):
        where.append("a.id IN (SELECT rowid FROM article_fts WHERE article_fts MATCH ?)")
        args.append(fts_query(f["q"]))
    if "risks" not in exclude and split_csv(f["risks"]):
        any_in("a.id IN (SELECT article_id FROM article_risk WHERE risk IN ({}))", split_csv(f["risks"]))
    if "risks" not in exclude and split_csv(f["categories"]):
        any_in("a.id IN (SELECT article_id FROM article_risk WHERE category IN ({}))", split_csv(f["categories"]))
    if "countries" not in exclude and split_csv(f["countries"]):
        if f["country_mode"] == "any":
            any_in("a.id IN (SELECT article_id FROM article_country WHERE cc IN ({}))", split_csv(f["countries"]))
        else:
            any_in("a.loc_cc IN ({})", split_csv(f["countries"]))
    if "langs" not in exclude and split_csv(f["langs"]):
        any_in("a.lang IN ({})", split_csv(f["langs"]))
    if f["feed"]:
        where.append("a.feed = ?")
        args.append(f["feed"])
    if "time" not in exclude and f["from"]:
        where.append("a.t >= ?")
        args.append(f["from"])
    if "time" not in exclude and f["to"]:
        where.append("a.t <= ?")
        args.append(f["to"])
    if f["tone_max"] is not None:
        where.append("a.tone <= ?")
        args.append(f["tone_max"])
    if f["src"]:
        where.append("a.src LIKE ?")
        args.append(f"%{f['src']}%")
    if "place" not in exclude and f["place"]:
        where.append("a.loc_name = ?")
        args.append(f["place"])
    if f["precise_loc"]:
        where.append("a.loc_type IN (3, 4)")
    return ("WHERE " + " AND ".join(where)) if where else "", args


def and_or_where(where):
    return "AND" if where else "WHERE"


def article_json(r):
    return {
        "id": r["id"], "t": r["t"], "seen": r["seen"], "pubExact": bool(r["pub_exact"]), "feed": r["feed"],
        "src": r["src"], "url": r["url"], "title": r["title"], "lang": r["lang"], "tone": r["tone"],
        "loc": None if r["loc_name"] is None else {
            "name": r["loc_name"], "type": r["loc_type"], "cc": r["loc_cc"], "country": r["loc_country"],
            "lat": r["lat"], "lon": r["lon"]},
        "places": json.loads(r["places"]), "orgs": json.loads(r["orgs"]), "counts": json.loads(r["counts"]),
        "risks": json.loads(r["risks"]), "themes": json.loads(r["themes"]),
    }


def run_search(f, sort, limit, offset):
    db = connect()
    order = {"new": "a.t DESC", "old": "a.t ASC", "tone": "a.tone ASC"}[sort]

    where, args = build_where(f)
    total = db.execute(f"SELECT count(*) FROM article a {where}", args).fetchone()[0]
    items = [article_json(r) for r in db.execute(
        f"SELECT a.* FROM article a {where} ORDER BY {order} LIMIT ? OFFSET ?", args + [limit, offset])]

    # Timeline ignores the time filter (the UI highlights the selection instead) and covers the
    # ingestion window only; a few pages carry publish dates from years ago
    window_start = db.execute("SELECT min(seen) FROM article").fetchone()[0][:13]
    w, a = build_where(f, exclude=("time",))
    timeline = [dict(r) for r in db.execute(
        f"SELECT a.hour AS hour, count(*) AS n FROM article a {w} {and_or_where(w)} a.hour >= ? "
        "GROUP BY a.hour ORDER BY a.hour", a + [window_start])]

    points = [dict(r) for r in db.execute(
        f"""SELECT a.loc_name AS name, a.loc_country AS country, a.lat AS lat, a.lon AS lon, count(*) AS n,
                   max(a.loc_type IN (3, 4)) AS precise
            FROM article a {where} {and_or_where(where)} a.lat IS NOT NULL
            GROUP BY a.loc_name ORDER BY n DESC LIMIT ?""", args + [MAP_POINTS])]

    # Facets ignore their own filter so you can see (and switch to) the alternatives
    w, a = build_where(f, exclude=("risks",))
    risk_facet = [dict(r) for r in db.execute(
        f"SELECT r.risk AS code, count(*) AS n FROM article_risk r JOIN article a ON a.id = r.article_id {w} "
        "GROUP BY r.risk ORDER BY n DESC", a)]
    w, a = build_where(f, exclude=("countries",))
    country_facet = [dict(r) for r in db.execute(
        f"SELECT a.loc_cc AS cc, a.loc_country AS name, count(*) AS n FROM article a {w} "
        f"{and_or_where(w)} a.loc_cc IS NOT NULL AND a.loc_cc != '' "
        "GROUP BY a.loc_cc ORDER BY n DESC LIMIT 60", a)]
    w, a = build_where(f, exclude=("langs",))
    lang_facet = [dict(r) for r in db.execute(
        f"SELECT a.lang AS code, count(*) AS n FROM article a {w} GROUP BY a.lang ORDER BY n DESC LIMIT 40", a)]
    source_facet = [dict(r) for r in db.execute(
        f"SELECT a.src AS src, count(*) AS n FROM article a {where} GROUP BY a.src ORDER BY n DESC LIMIT 15", args)]

    return {
        "total": total, "limit": limit, "offset": offset, "items": items, "timeline": timeline, "points": points,
        "facets": {"risks": risk_facet, "countries": country_facet, "langs": lang_facet, "sources": source_facet},
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GDELT Risk Explorer API",
    version="0.1.0",
    description=(
        "Read-only access to supply-chain risk articles extracted from GDELT 2.0 GKG "
        "(English + machine-translated feeds).\n\n"
        "Country codes are FIPS 10-4 (GDELT's), not ISO. Times are UTC.\n\n"
        "Data source: The GDELT Project (gdeltproject.org)."
    ),
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "Articles", "description": "Search and fetch risk articles"},
        {"name": "Dataset", "description": "What is in the database and how risk types are defined"},
    ],
)


@app.exception_handler(sqlite3.OperationalError)
def sqlite_error(_: Request, exc: sqlite3.OperationalError):
    return JSONResponse({"detail": f"Query error: {exc}"}, status_code=400)


@app.get("/api/meta", response_model=Meta, response_model_by_alias=True, tags=["Dataset"],
         summary="Dataset overview and risk taxonomy")
def meta():
    db = connect()
    row = db.execute("SELECT count(*) AS n, min(seen) AS t0, max(seen) AS t1 FROM article").fetchone()
    feeds = dict(db.execute("SELECT feed, count(*) FROM article GROUP BY feed").fetchall())
    batches = dict(db.execute("SELECT status, count(*) FROM batch GROUP BY status").fetchall())
    scanned = db.execute("SELECT sum(scanned) FROM batch").fetchone()[0]
    return {"total": row["n"], "from": row["t0"], "to": row["t1"], "feeds": feeds, "batches": batches,
            "scanned": scanned, **as_json()}


@app.get("/api/search", response_model=SearchResponse, tags=["Articles"],
         summary="Search and filter risk articles",
         description="All filters are optional and combine with AND. Lists are comma-separated; "
                     "values within one list combine with OR.")
def search(
    q: Optional[str] = Query(None, description='Full-text search over headline, organisations, places and source. '
                             'All words must match (stemmed). "Quoted text" = phrase, word* = prefix.',
                             examples=["port strike"]),
    risks: Optional[str] = Query(None, description="Risk-type codes, comma-separated (see /api/meta)",
                                 examples=["fire,explosion"]),
    categories: Optional[str] = Query(None, description="Risk-category codes, comma-separated",
                                      examples=["natural,industrial"]),
    countries: Optional[str] = Query(None, description="FIPS country codes, comma-separated (GM = Germany, CH = China)",
                                     examples=["ID,VM"]),
    country_mode: Literal["primary", "any"] = Query("primary", description="primary = country of the best-guess "
                                                     "event location; any = any country mentioned in the article"),
    langs: Optional[str] = Query(None, description="ISO 639 source-language codes, comma-separated",
                                 examples=["ind,vie"]),
    feed: Optional[Literal["en", "translated"]] = Query(None, description="Only English or only translated sources"),
    from_: Optional[str] = Query(None, alias="from", description="Earliest publish time (UTC, ISO 8601)",
                                 examples=["2026-10-20T00:00:00Z"]),
    to: Optional[str] = Query(None, description="Latest publish time (UTC, ISO 8601)",
                              examples=["2026-10-20T23:59:59Z"]),
    tone_max: Optional[float] = Query(None, description="Only articles with tone at or below this value", examples=[-3]),
    src: Optional[str] = Query(None, description="Source domain contains this text", examples=["reuters"]),
    place: Optional[str] = Query(None, description="Exact event-location name (as returned in `loc.name`)"),
    precise_loc: bool = Query(False, description="Only articles with a city-level event location"),
    sort: Literal["new", "old", "tone"] = Query("new", description="new / old by publish time, tone = most negative first"),
    limit: int = Query(50, ge=1, le=MAX_LIMIT, description="Page size"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
):
    filters = {"q": q, "risks": risks, "categories": categories, "countries": countries,
               "country_mode": country_mode, "langs": langs, "feed": feed, "from": from_, "to": to,
               "tone_max": tone_max, "src": src, "place": place, "precise_loc": precise_loc}
    return run_search(filters, sort, limit, offset)


@app.get("/api/articles/{article_id}", response_model=Article, tags=["Articles"], summary="Get one article by id")
def get_article(article_id: int):
    row = connect().execute("SELECT * FROM article WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Article not found")
    return article_json(row)


if __name__ == "__main__":
    print(f"API on http://localhost:{PORT}  ·  Swagger UI: http://localhost:{PORT}/api/docs", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
