import { useMemo, useState, type ReactNode } from "react";
import { CATEGORY_COLORS, Filters, Meta, SearchResult, fmtNum, langName } from "./lib";

type Props = {
  meta: Meta | null;
  filters: Filters;
  facets: SearchResult["facets"] | null;
  update: (patch: Partial<Filters>) => void;
};

const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export default function Sidebar({ meta, filters, facets, update }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [countryQ, setCountryQ] = useState("");
  const [showAllLangs, setShowAllLangs] = useState(false);

  const riskCount = useMemo(() => {
    const m: Record<string, number> = {};
    facets?.risks.forEach((r) => (m[r.code] = r.n));
    return m;
  }, [facets]);

  const quickRange = (hours: number | null) => {
    if (!meta || hours === null) return update({ from: "", to: "" });
    const end = Date.parse(meta.to) + 15 * 60000;
    update({ from: new Date(end - hours * 3600000).toISOString().slice(0, 16) + ":00Z", to: "" });
  };

  const countries = (facets?.countries ?? []).filter(
    (c) => !countryQ || c.name.toLowerCase().includes(countryQ.toLowerCase()) || c.cc.toLowerCase() === countryQ.toLowerCase(),
  );
  const langs = facets?.langs ?? [];

  return (
    <aside className="sidebar">
      <Section title="Time">
        <div className="pills">
          {[["6h", 6], ["12h", 12], ["24h", 24], ["All 48h", null]].map(([label, h]) => (
            <button key={label as string} className="pill" onClick={() => quickRange(h as number | null)}>{label}</button>
          ))}
        </div>
      </Section>

      <Section title="Risk type" action={filters.risks.length ? <button className="link" onClick={() => update({ risks: [] })}>Clear</button> : null}>
        {meta?.categories.map((cat) => {
          const types = meta.riskTypes.filter((r) => r.category === cat.code);
          const codes = types.map((t) => t.code);
          const selected = codes.filter((c) => filters.risks.includes(c)).length;
          const total = codes.reduce((s, c) => s + (riskCount[c] ?? 0), 0);
          const isOpen = open[cat.code] ?? selected > 0;
          return (
            <div key={cat.code} className="cat">
              <div className="cat-row">
                <input
                  type="checkbox"
                  checked={selected === codes.length}
                  ref={(el) => { if (el) el.indeterminate = selected > 0 && selected < codes.length; }}
                  onChange={() =>
                    update({
                      risks: selected === codes.length
                        ? filters.risks.filter((r) => !codes.includes(r))
                        : [...new Set([...filters.risks, ...codes])],
                    })}
                />
                <span className="dot" style={{ background: CATEGORY_COLORS[cat.code] }} />
                <button className="cat-name" onClick={() => setOpen({ ...open, [cat.code]: !isOpen })}>
                  {cat.label} <span className="caret">{isOpen ? "▾" : "▸"}</span>
                </button>
                <span className="count" title="Sum of risk-type matches; an article can match several">{fmtNum(total)}</span>
              </div>
              {isOpen && types.map((t) => (
                <label key={t.code} className="opt sub" title={`GDELT themes: ${t.gdeltThemes.join(", ")}`}>
                  <input type="checkbox" checked={filters.risks.includes(t.code)}
                    onChange={() => update({ risks: toggle(filters.risks, t.code) })} />
                  <span className="opt-label">{t.label}</span>
                  <span className="count">{fmtNum(riskCount[t.code] ?? 0)}</span>
                </label>
              ))}
            </div>
          );
        })}
      </Section>

      <Section title="Country" action={filters.countries.length ? <button className="link" onClick={() => update({ countries: [] })}>Clear</button> : null}>
        <div className="seg small">
          <button className={filters.countryMode === "primary" ? "on" : ""} onClick={() => update({ countryMode: "primary" })}
            title="Country of the best-guess event location">Event location</button>
          <button className={filters.countryMode === "any" ? "on" : ""} onClick={() => update({ countryMode: "any" })}
            title="Any country mentioned in the article">Any mention</button>
        </div>
        <input className="mini-search" placeholder="Filter countries…" value={countryQ} onChange={(e) => setCountryQ(e.target.value)} />
        <div className="scroll-list">
          {countries.map((c) => (
            <label key={c.cc} className="opt">
              <input type="checkbox" checked={filters.countries.includes(c.cc)}
                onChange={() => update({ countries: toggle(filters.countries, c.cc) })} />
              <span className="opt-label">{c.name}</span>
              <span className="count">{fmtNum(c.n)}</span>
            </label>
          ))}
        </div>
        <p className="hint">Counts by event location. GDELT uses FIPS codes (e.g. GM = Germany).</p>
      </Section>

      <Section title="Language">
        <div className="seg small">
          {([["", "All"], ["en", "English sources"], ["translated", "Translated"]] as const).map(([v, label]) => (
            <button key={v} className={filters.feed === v ? "on" : ""} onClick={() => update({ feed: v })}>{label}</button>
          ))}
        </div>
        <div className={showAllLangs ? "scroll-list" : ""}>
          {(showAllLangs ? langs : langs.slice(0, 8)).map((l) => (
            <label key={l.code} className="opt">
              <input type="checkbox" checked={filters.langs.includes(l.code)}
                onChange={() => update({ langs: toggle(filters.langs, l.code) })} />
              <span className="opt-label">{langName(l.code)}</span>
              <span className="count">{fmtNum(l.n)}</span>
            </label>
          ))}
        </div>
        {langs.length > 8 && (
          <button className="link" onClick={() => setShowAllLangs(!showAllLangs)}>
            {showAllLangs ? "Show fewer" : `Show all ${langs.length}`}
          </button>
        )}
        <p className="hint">Translated articles keep their original-language headline. Places and organisations are in English.</p>
      </Section>

      <Section title="Tone">
        <select value={filters.toneMax} onChange={(e) => update({ toneMax: e.target.value })}>
          <option value="">Any tone</option>
          <option value="0">Negative (≤ 0)</option>
          <option value="-3">Clearly negative (≤ −3)</option>
          <option value="-6">Very negative (≤ −6)</option>
        </select>
      </Section>

      <Section title="Location quality">
        <label className="opt">
          <input type="checkbox" checked={filters.preciseLoc} onChange={(e) => update({ preciseLoc: e.target.checked })} />
          <span className="opt-label">City-level only (hide country/region centroids)</span>
        </label>
      </Section>

      <Section title="Source">
        <input className="mini-search" placeholder="Domain contains… e.g. reuters" value={filters.src}
          onChange={(e) => update({ src: e.target.value })} />
        {facets?.sources.slice(0, 8).map((s) => (
          <button key={s.src} className="opt as-btn" onClick={() => update({ src: s.src })}>
            <span className="opt-label">{s.src}</span>
            <span className="count">{fmtNum(s.n)}</span>
          </button>
        ))}
      </Section>
    </aside>
  );
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="side-section">
      <div className="side-head">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}
