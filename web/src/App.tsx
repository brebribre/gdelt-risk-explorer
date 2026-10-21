import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Article, EMPTY_FILTERS, Filters, Meta, SearchResult, apiParams, filtersToParams, fmtNum, fmtUtc, langName,
  paramsToFilters,
} from "./lib";
import Sidebar from "./Sidebar";
import Timeline from "./Timeline";
import MapView from "./MapView";
import ArticleCard from "./ArticleCard";

const PAGE = 50;

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [filters, setFilters] = useState<Filters>(() => paramsToFilters(new URLSearchParams(location.search)));
  const [qInput, setQInput] = useState(filters.q);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [items, setItems] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"split" | "list" | "map">("split");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/meta").then((r) => r.json()).then(setMeta).catch((e) => setError(String(e)));
  }, []);

  // Debounce the search box
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => (f.q === qInput ? f : { ...f, q: qInput })), 300);
    return () => clearTimeout(t);
  }, [qInput]);

  // Keep the URL shareable
  useEffect(() => {
    const qs = filtersToParams(filters).toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  }, [filters]);

  const load = useCallback(async (f: Filters, offset: number) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/search?${apiParams(f, offset, PAGE)}`, { signal: ctrl.signal });
      const body = await r.json();
      if (!r.ok) throw new Error(body.error ?? r.statusText);
      setResult(body);
      setItems((prev) => (offset === 0 ? body.items : [...prev, ...body.items]));
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError(String(e));
    } finally {
      if (abortRef.current === ctrl) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters, 0);
  }, [filters, load]);

  const update = useCallback((patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch })), []);
  const searchFor = useCallback((text: string) => {
    const q = /\s/.test(text) ? `"${text}"` : text;
    setQInput(q);
    setFilters((f) => ({ ...f, q }));
  }, []);
  const reset = () => {
    setQInput("");
    setFilters(EMPTY_FILTERS);
  };

  const riskLabel = useMemo(() => {
    const m: Record<string, { label: string; category: string }> = {};
    meta?.riskTypes.forEach((r) => (m[r.code] = r));
    return m;
  }, [meta]);
  const countryNames = useMemo(() => {
    const m: Record<string, string> = {};
    result?.facets.countries.forEach((c) => (m[c.cc] = c.name));
    return m;
  }, [result]);

  const chips: { key: string; label: string; clear: () => void }[] = [];
  if (filters.q) chips.push({ key: "q", label: `Search: ${filters.q}`, clear: () => { setQInput(""); update({ q: "" }); } });
  filters.risks.forEach((r) =>
    chips.push({ key: `r-${r}`, label: riskLabel[r]?.label ?? r, clear: () => update({ risks: filters.risks.filter((x) => x !== r) }) }));
  filters.countries.forEach((c) =>
    chips.push({ key: `c-${c}`, label: `${countryNames[c] ?? c}${filters.countryMode === "any" ? " (mentioned)" : ""}`, clear: () => update({ countries: filters.countries.filter((x) => x !== c) }) }));
  filters.langs.forEach((l) =>
    chips.push({ key: `l-${l}`, label: langName(l), clear: () => update({ langs: filters.langs.filter((x) => x !== l) }) }));
  if (filters.feed) chips.push({ key: "feed", label: filters.feed === "en" ? "English sources" : "Translated sources", clear: () => update({ feed: "" }) });
  if (filters.place) chips.push({ key: "place", label: `Place: ${filters.place}`, clear: () => update({ place: "" }) });
  if (filters.from || filters.to)
    chips.push({ key: "time", label: `${filters.from ? fmtUtc(filters.from) : "…"} → ${filters.to ? fmtUtc(filters.to) : "…"}`, clear: () => update({ from: "", to: "" }) });
  if (filters.toneMax) chips.push({ key: "tone", label: `Tone ≤ ${filters.toneMax}`, clear: () => update({ toneMax: "" }) });
  if (filters.src) chips.push({ key: "src", label: `Source: ${filters.src}`, clear: () => update({ src: "" }) });
  if (filters.preciseLoc) chips.push({ key: "precise", label: "City-level location", clear: () => update({ preciseLoc: false }) });

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◎</span>
          <div>
            <h1>GDELT Risk Explorer</h1>
            {meta && (
              <p className="subtitle">
                {fmtNum(meta.total)} risk articles from {fmtNum(meta.scanned)} scanned · {fmtUtc(meta.from)} → {fmtUtc(meta.to)}
              </p>
            )}
          </div>
        </div>
        <div className="search">
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder='Search headlines, companies, places, sources… e.g. port strike, "Foxconn", Bekasi'
            autoFocus
          />
          {qInput && <button className="clear-x" onClick={() => setQInput("")} aria-label="Clear search">×</button>}
        </div>
        <div className="top-controls">
          <select value={filters.sort} onChange={(e) => update({ sort: e.target.value as Filters["sort"] })}>
            <option value="new">Newest first</option>
            <option value="old">Oldest first</option>
            <option value="tone">Most negative first</option>
          </select>
          <div className="seg">
            {(["split", "list", "map"] as const).map((v) => (
              <button key={v} className={view === v ? "on" : ""} onClick={() => setView(v)}>
                {v === "split" ? "Split" : v === "list" ? "List" : "Map"}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="body">
        <Sidebar meta={meta} filters={filters} facets={result?.facets ?? null} update={update} />

        <main className="main">
          <section className="panel timeline-panel">
            <div className="panel-head">
              <span>Articles per hour (UTC)</span>
              <span className="muted">Drag to select a time range</span>
            </div>
            <Timeline meta={meta} data={result?.timeline ?? []} from={filters.from} to={filters.to}
              onSelect={(from, to) => update({ from, to })} />
          </section>

          <div className="resultbar">
            <strong>{result ? fmtNum(result.total) : "…"}</strong>&nbsp;articles
            {loading && <span className="spinner" aria-label="Loading" />}
            <div className="chips">
              {chips.map((c) => (
                <button key={c.key} className="chip" onClick={c.clear} title="Remove filter">
                  {c.label} <span>×</span>
                </button>
              ))}
              {chips.length > 0 && <button className="link" onClick={reset}>Clear all</button>}
            </div>
          </div>
          {error && <div className="error">Error: {error}. Is the API running on port 8787?</div>}

          <div className={`content view-${view}`}>
            {view !== "map" && (
              <section className="list">
                {items.map((a) => (
                  <ArticleCard key={a.id} a={a} riskLabel={riskLabel} now={Date.now()}
                    onOrg={searchFor} onPlace={(p) => update({ place: p })} onSource={(s) => update({ src: s })} />
                ))}
                {result && items.length < result.total && (
                  <button className="more" disabled={loading} onClick={() => load(filters, items.length)}>
                    {loading ? "Loading…" : `Load more (${fmtNum(result.total - items.length)} left)`}
                  </button>
                )}
                {result && result.total === 0 && <div className="empty">No articles match these filters.</div>}
              </section>
            )}
            {view !== "list" && (
              <section className="mapwrap">
                <MapView points={result?.points ?? []} selected={filters.place} onSelect={(p) => update({ place: p })} />
                <div className="map-note">
                  Circles = best-guess event location (place mentioned closest to the risk keyword). Size = article count. Click to filter.
                </div>
              </section>
            )}
          </div>
        </main>
      </div>
      <footer className="foot">Data source: The GDELT Project (gdeltproject.org). Headlines link to the original publishers.</footer>
    </div>
  );
}
