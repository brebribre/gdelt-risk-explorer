"""Download GDELT GKG batches for the last N hours, keep risk-relevant articles,
and store them in a SQLite database (with full-text search) for the API.

Usage:
    python3 ingest.py                 # last 48h, English + translated feeds
    python3 ingest.py --hours 2       # quick test
    python3 ingest.py --feeds en      # English only

Re-running is incremental: batches already ingested are skipped.
Raw files are processed in memory and never written to disk.
"""

import argparse
import csv
import html
import io
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from taxonomy import RISK_TYPES, THEME_TO_RISK

BASE = "http://data.gdeltproject.org/gdeltv2/"
FEEDS = {
    "en": ("lastupdate.txt", "{ts}.gkg.csv.zip"),
    "translated": ("lastupdate-translation.txt", "{ts}.translation.gkg.csv.zip"),
}
HERE = Path(__file__).resolve().parent
DB_PATH = HERE.parent / "data" / "gdelt.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS article (
    id INTEGER PRIMARY KEY,
    gkg_id TEXT, url TEXT UNIQUE, t TEXT, seen TEXT, pub_exact INTEGER, hour TEXT, feed TEXT, src TEXT, title TEXT, lang TEXT, tone REAL,
    loc_name TEXT, loc_type INTEGER, loc_cc TEXT, loc_country TEXT, lat REAL, lon REAL,
    places TEXT, orgs TEXT, counts TEXT, themes TEXT, risks TEXT
);
CREATE INDEX IF NOT EXISTS article_t ON article(t);
CREATE TABLE IF NOT EXISTS article_risk (article_id INTEGER, risk TEXT, category TEXT);
CREATE INDEX IF NOT EXISTS article_risk_r ON article_risk(risk, article_id);
CREATE INDEX IF NOT EXISTS article_risk_c ON article_risk(category, article_id);
CREATE INDEX IF NOT EXISTS article_risk_a ON article_risk(article_id);
CREATE TABLE IF NOT EXISTS article_country (article_id INTEGER, cc TEXT);
CREATE INDEX IF NOT EXISTS article_country_cc ON article_country(cc, article_id);
CREATE INDEX IF NOT EXISTS article_country_a ON article_country(article_id);
CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(title, orgs, places, src, tokenize='porter unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS batch (feed TEXT, ts TEXT, status TEXT, scanned INTEGER, kept INTEGER, PRIMARY KEY (feed, ts));
"""

# GKG 2.1 column indexes
C_ID, C_DATE, C_SRC, C_URL = 0, 1, 3, 4
C_COUNTS, C_THEMES, C_LOCS, C_ORGS, C_TONE, C_TRANS, C_EXTRAS = 6, 8, 10, 14, 15, 25, 26

# Location types: 1 country, 2 US state, 3 US city, 4 world city, 5 world ADM1.
# Penalty (in characters) so the nearest *specific* place wins over a country mention.
LOC_PENALTY = {1: 1500, 2: 600, 5: 600, 3: 0, 4: 0}

csv.field_size_limit(10**9)


def load_countries():
    names = {}
    for line in (HERE / "fips_countries.tsv").read_text(encoding="utf-8").splitlines():
        code, _, name = line.partition("\t")
        if code:
            names[code.strip()] = name.strip()
    return names


def latest_timestamp(feed):
    index, _ = FEEDS[feed]
    with urllib.request.urlopen(BASE + index, timeout=30) as r:
        line = r.read().decode().splitlines()[0]
    return re.search(r"/(\d{14})\.", line).group(1)


def batch_timestamps(latest, hours):
    end = datetime.strptime(latest, "%Y%m%d%H%M%S")
    return [(end - timedelta(minutes=15 * i)).strftime("%Y%m%d%H%M%S") for i in range(hours * 4)]


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # GDELT occasionally skips a batch
            err = e
        except Exception as e:  # network hiccup: retry
            err = e
        time.sleep(2 * (attempt + 1))
    raise err


def split_items(field, sep):
    return [item.split(sep) for item in field.split(";") if item]

#a raw GKG row becomes the app's article record.
def parse_row(r, countries):
    if len(r) < 27:
        return None

    # Themes -> our risk types, with offsets for location pairing
    risk_offsets = {}
    gdelt_themes = set()
    #check the row len and extract risk matches form the theme field
    #offset is the theme's position in the text
    for parts in split_items(r[C_THEMES], ","):
        theme = parts[0]
        risk = THEME_TO_RISK.get(theme)
        if not risk:
            continue
        gdelt_themes.add(theme)
        try:
            risk_offsets.setdefault(risk, []).append(int(parts[1]))
        except (IndexError, ValueError):
            risk_offsets.setdefault(risk, [])
    if not risk_offsets:
        return None

    # Locations: dedupe by name, remember every mention offset
    locs = {}
    for p in split_items(r[C_LOCS], "#"):
        if len(p) < 9:
            continue
        try:
            ltype, lat, lon, off = int(p[0]), float(p[5]), float(p[6]), int(p[8])
        except ValueError:
            continue
        loc = locs.setdefault(p[1], {
            "name": p[1], "type": ltype, "cc": p[2], "country": countries.get(p[2], p[2]),
            "adm1": p[3], "lat": round(lat, 4), "lon": round(lon, 4), "offsets": [],
        })
        loc["offsets"].append(off)

    # Primary location: the place mentioned closest to a risk theme
    all_risk_offsets = [o for offs in risk_offsets.values() for o in offs]
    primary = None
    if locs:
        def score(loc):
            dist = min((abs(a - b) for a in loc["offsets"] for b in all_risk_offsets), default=10**6)
            return dist + LOC_PENALTY.get(loc["type"], 0)
        primary = min(locs.values(), key=score)

    orgs, seen = [], set()
    for item in r[C_ORGS].split(";"):
        name = item.rsplit(",", 1)[0].strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            orgs.append(name)

    counts, seen = [], set()
    for p in split_items(r[C_COUNTS], "#"):
        if len(p) < 3 or not p[1].isdigit():
            continue
        key = (p[0], p[1], p[2])
        if key not in seen:
            seen.add(key)
            counts.append({"type": p[0], "n": int(p[1]), "object": p[2]})

    m = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", r[C_EXTRAS], re.S)
    title = html.unescape(m.group(1)).strip() if m else ""
    lang = re.search(r"srclc:(\w+)", r[C_TRANS])
    try:
        tone = round(float(r[C_TONE].split(",")[0]), 1)
    except ValueError:
        tone = 0.0

    # Batch time = when GDELT saw it. Prefer the page's own publish time when present.
    # parser distinguishes the time GDELT saw an article from its publication time.
    #precise publication timestamp when that timestamp is present, otherwise use the GDELT batch time.
    seen = r[C_DATE]
    p = re.search(r"<PAGE_PRECISEPUBTIMESTAMP>(\d{14})", r[C_EXTRAS])
    pub = p.group(1) if p and "2000" < p.group(1) <= seen else None
    d = pub or seen
    return {
        "id": r[C_ID],
        "t": f"{d[0:4]}-{d[4:6]}-{d[6:8]}T{d[8:10]}:{d[10:12]}:00Z",
        "seen": f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}T{seen[8:10]}:{seen[10:12]}:00Z",
        "pubExact": pub is not None,
        "src": r[C_SRC],
        "url": r[C_URL],
        "title": title,
        "lang": lang.group(1) if lang else "eng",
        "tone": tone,
        "risks": sorted(risk_offsets),
        "themes": sorted(gdelt_themes),
        "loc": None if not primary else {k: primary[k] for k in ("name", "type", "cc", "country", "lat", "lon")},
        "places": [l["name"] for l in sorted(locs.values(), key=lambda l: l["offsets"][0])][:8],
        "countries": sorted({l["cc"] for l in locs.values() if l["cc"]}),
        "orgs": orgs[:10],
        "counts": counts[:6],
    }


def process_batch(feed, ts, countries):
    url = BASE + FEEDS[feed][1].format(ts=ts)
    data = fetch(url)
    if data is None:
        return feed, ts, None, 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    rows = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    out, total = [], 0
    for r in rows:
        total += 1
        rec = parse_row(r, countries)
        if rec:
            out.append(rec)
    return feed, ts, out, total


def store(db, feed, recs):
    kept = 0
    for a in recs:
        loc = a["loc"] or {}
        cur = db.execute(
            "INSERT OR IGNORE INTO article (gkg_id, url, t, seen, pub_exact, hour, feed, src, title, lang, tone,"
            " loc_name, loc_type, loc_cc, loc_country, lat, lon, places, orgs, counts, themes, risks)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a["id"], a["url"], a["t"], a["seen"], int(a["pubExact"]), a["t"][:13], feed, a["src"], a["title"], a["lang"], a["tone"],
             loc.get("name"), loc.get("type"), loc.get("cc"), loc.get("country"), loc.get("lat"), loc.get("lon"),
             json.dumps(a["places"]), json.dumps(a["orgs"]), json.dumps(a["counts"]),
             json.dumps(a["themes"]), json.dumps(a["risks"])))
        if cur.rowcount == 0:
            continue  # same URL already stored
        kept += 1
        aid = cur.lastrowid
        db.executemany("INSERT INTO article_risk VALUES (?,?,?)",
                       [(aid, r, RISK_TYPES[r][0]) for r in a["risks"]])
        db.executemany("INSERT INTO article_country VALUES (?,?)", [(aid, cc) for cc in a["countries"]])
        db.execute("INSERT INTO article_fts (rowid, title, orgs, places, src) VALUES (?,?,?,?,?)",
                   (aid, a["title"], " ; ".join(a["orgs"]), " ; ".join(a["places"]), a["src"]))
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--feeds", default="en,translated")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    done_batches = {(f, ts) for f, ts in db.execute("SELECT feed, ts FROM batch WHERE status = 'ok'")}

    countries = load_countries()
    feeds = [f.strip() for f in args.feeds.split(",") if f.strip()]
    jobs = [(f, ts) for f in feeds for ts in batch_timestamps(latest_timestamp(f), args.hours)
            if (f, ts) not in done_batches]
    print(f"{len(jobs)} new batches to fetch ({', '.join(feeds)}, {args.hours}h)", flush=True)

    stats = {"ok": 0, "missing": 0, "failed": 0, "scanned": 0, "kept": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_batch, f, ts, countries): (f, ts) for f, ts in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            f, ts = futures[fut]
            try:
                _, _, recs, total = fut.result()
            except Exception as e:
                stats["failed"] += 1
                print(f"  failed {f} {ts}: {e}", file=sys.stderr, flush=True)
                continue
            if recs is None:
                stats["missing"] += 1
                db.execute("INSERT OR REPLACE INTO batch VALUES (?,?,?,?,?)", (f, ts, "missing", 0, 0))
                continue
            with db:
                kept = store(db, f, recs)
                db.execute("INSERT OR REPLACE INTO batch VALUES (?,?,?,?,?)", (f, ts, "ok", total, kept))
            stats["ok"] += 1
            stats["scanned"] += total
            stats["kept"] += kept
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} batches, {stats['kept']} risk articles stored", flush=True)

    db.commit()
    total = db.execute("SELECT count(*) FROM article").fetchone()[0]
    print(f"done: {stats}. Database now holds {total} articles ({DB_PATH.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
