"""Small read-only JSON API over the SQLite database built by ingest/ingest.py.

    python3 server/api.py            # serves on http://localhost:8787

GET /api/meta     taxonomy, date range, totals
GET /api/search   filtered results + facets + timeline + map points
"""

import json
import re
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingest"))
from taxonomy import as_json  # noqa: E402

DB_PATH = ROOT / "data" / "gdelt.db"
PORT = 8787
MAX_LIMIT = 200
MAP_POINTS = 1500


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


def csv_param(qs, key):
    return [v for v in ",".join(qs.get(key, [])).split(",") if v]


def build_where(qs, exclude=()):
    """WHERE clause for the filters in the query string. `exclude` skips filters (for facet counts)."""
    where, args = [], []

    def one(key):
        v = qs.get(key, [""])[0].strip()
        return v or None

    if "q" not in exclude and one("q"):
        fq = fts_query(one("q"))
        if fq:
            where.append("a.id IN (SELECT rowid FROM article_fts WHERE article_fts MATCH ?)")
            args.append(fq)
    if "risks" not in exclude and csv_param(qs, "risks"):
        vals = csv_param(qs, "risks")
        where.append(f"a.id IN (SELECT article_id FROM article_risk WHERE risk IN ({','.join('?' * len(vals))}))")
        args += vals
    if "categories" not in exclude and csv_param(qs, "categories"):
        vals = csv_param(qs, "categories")
        where.append(f"a.id IN (SELECT article_id FROM article_risk WHERE category IN ({','.join('?' * len(vals))}))")
        args += vals
    if "countries" not in exclude and csv_param(qs, "countries"):
        vals = csv_param(qs, "countries")
        marks = ",".join("?" * len(vals))
        if one("country_mode") == "any":
            where.append(f"a.id IN (SELECT article_id FROM article_country WHERE cc IN ({marks}))")
        else:
            where.append(f"a.loc_cc IN ({marks})")
        args += vals
    if "langs" not in exclude and csv_param(qs, "langs"):
        vals = csv_param(qs, "langs")
        where.append(f"a.lang IN ({','.join('?' * len(vals))})")
        args += vals
    if one("feed"):
        where.append("a.feed = ?")
        args.append(one("feed"))
    if "time" not in exclude and one("from"):
        where.append("a.t >= ?")
        args.append(one("from"))
    if "time" not in exclude and one("to"):
        where.append("a.t <= ?")
        args.append(one("to"))
    if one("tone_max"):
        where.append("a.tone <= ?")
        args.append(float(one("tone_max")))
    if one("src"):
        where.append("a.src LIKE ?")
        args.append(f"%{one('src')}%")
    if "place" not in exclude and one("place"):
        where.append("a.loc_name = ?")
        args.append(one("place"))
    if one("precise_loc") == "1":
        where.append("a.loc_type IN (3, 4)")
    return ("WHERE " + " AND ".join(where)) if where else "", args


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


def search(qs):
    db = connect()
    limit = min(int(qs.get("limit", ["50"])[0]), MAX_LIMIT)
    offset = int(qs.get("offset", ["0"])[0])
    order = {"new": "a.t DESC", "old": "a.t ASC", "tone": "a.tone ASC"}.get(qs.get("sort", ["new"])[0], "a.t DESC")

    where, args = build_where(qs)
    total = db.execute(f"SELECT count(*) FROM article a {where}", args).fetchone()[0]
    items = [article_json(r) for r in db.execute(
        f"SELECT a.* FROM article a {where} ORDER BY {order} LIMIT ? OFFSET ?", args + [limit, offset])]

    # Timeline ignores the time filter (the UI highlights the selection instead) and covers the
    # ingestion window only; a few pages carry publish dates from years ago
    window_start = db.execute("SELECT min(seen) FROM article").fetchone()[0][:13]
    w, a = build_where(qs, exclude=("time",))
    timeline = [dict(r) for r in db.execute(
        f"SELECT a.hour AS hour, count(*) AS n FROM article a {w} {'AND' if w else 'WHERE'} a.hour >= ? "
        "GROUP BY a.hour ORDER BY a.hour", a + [window_start])]

    points = [dict(r) for r in db.execute(
        f"""SELECT a.loc_name AS name, a.loc_country AS country, a.lat AS lat, a.lon AS lon, count(*) AS n,
                   max(a.loc_type IN (3, 4)) AS precise
            FROM article a {where} {'AND' if where else 'WHERE'} a.lat IS NOT NULL
            GROUP BY a.loc_name ORDER BY n DESC LIMIT ?""", args + [MAP_POINTS])]

    # Facets ignore their own filter so you can see (and switch to) the alternatives
    w, a = build_where(qs, exclude=("risks", "categories"))
    risk_facet = [dict(r) for r in db.execute(
        f"SELECT r.risk AS code, count(*) AS n FROM article_risk r JOIN article a ON a.id = r.article_id {w} "
        "GROUP BY r.risk ORDER BY n DESC", a)]
    w, a = build_where(qs, exclude=("countries",))
    country_facet = [dict(r) for r in db.execute(
        f"SELECT a.loc_cc AS cc, a.loc_country AS name, count(*) AS n FROM article a {w} "
        f"{'AND' if w else 'WHERE'} a.loc_cc IS NOT NULL AND a.loc_cc != '' "
        "GROUP BY a.loc_cc ORDER BY n DESC LIMIT 60", a)]
    w, a = build_where(qs, exclude=("langs",))
    lang_facet = [dict(r) for r in db.execute(
        f"SELECT a.lang AS code, count(*) AS n FROM article a {w} GROUP BY a.lang ORDER BY n DESC LIMIT 40", a)]
    source_facet = [dict(r) for r in db.execute(
        f"SELECT a.src AS src, count(*) AS n FROM article a {where} GROUP BY a.src ORDER BY n DESC LIMIT 15", args)]

    return {
        "total": total, "limit": limit, "offset": offset, "items": items, "timeline": timeline, "points": points,
        "facets": {"risks": risk_facet, "countries": country_facet, "langs": lang_facet, "sources": source_facet},
    }


def meta():
    db = connect()
    row = db.execute("SELECT count(*) AS n, min(seen) AS t0, max(seen) AS t1 FROM article").fetchone()
    feeds = dict(db.execute("SELECT feed, count(*) FROM article GROUP BY feed").fetchall())
    batches = dict(db.execute("SELECT status, count(*) FROM batch GROUP BY status").fetchall())
    scanned = db.execute("SELECT sum(scanned) FROM batch").fetchone()[0]
    return {"total": row["n"], "from": row["t0"], "to": row["t1"], "feeds": feeds, "batches": batches,
            "scanned": scanned, **as_json()}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        started = time.time()
        try:
            if url.path == "/api/meta":
                body = meta()
            elif url.path == "/api/search":
                body = search(qs)
            else:
                return self.send_json({"error": "not found"}, 404)
            self.send_json(body)
        except (sqlite3.OperationalError, ValueError) as e:
            self.send_json({"error": str(e)}, 400)
        finally:
            sys.stderr.write(f"{url.path}?{url.query} {(time.time() - started) * 1000:.0f}ms\n")

    def send_json(self, body, status=200):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"API on http://localhost:{PORT} (db: {DB_PATH})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
