import { useState } from "react";
import { Article, CATEGORY_COLORS, fmtUtc, langName, timeAgo } from "./lib";

type Props = {
  a: Article;
  riskLabel: Record<string, { label: string; category: string }>;
  now: number;
  onOrg: (org: string) => void;
  onPlace: (place: string) => void;
  onSource: (src: string) => void;
};

const COUNT_LABELS: Record<string, string> = {
  KILL: "killed", WOUND: "wounded", AFFECT: "affected", ARREST: "arrested", KIDNAP: "kidnapped",
  PROTEST: "protesters", SEIZE: "seized",
};

export default function ArticleCard({ a, riskLabel, now, onOrg, onPlace, onSource }: Props) {
  const [open, setOpen] = useState(false);
  const staleHours = (Date.parse(a.seen) - Date.parse(a.t)) / 3600000;
  const counts = a.counts.filter((c) => COUNT_LABELS[c.type]);

  return (
    <article className="card">
      <div className="badges">
        {a.risks.map((r) => {
          const info = riskLabel[r];
          const color = CATEGORY_COLORS[info?.category ?? ""] ?? "#666";
          return (
            <span key={r} className="badge" style={{ color, borderColor: color }}>{info?.label ?? r}</span>
          );
        })}
      </div>
      <h2>
        <a href={a.url} target="_blank" rel="noreferrer noopener">{a.title || a.url}</a>
      </h2>
      <div className="meta-line">
        <button className="link" onClick={() => onSource(a.src)}>{a.src}</button>
        <span title={`Published ${fmtUtc(a.t)}${a.pubExact ? "" : " (GDELT batch time)"} · seen by GDELT ${fmtUtc(a.seen)}`}>
          {timeAgo(a.t, now)}
        </span>
        {a.lang !== "eng" && <span className="lang">{langName(a.lang)}</span>}
        {staleHours > 24 && <span className="stale" title="Published long before GDELT saw it">old article · {fmtUtc(a.t).slice(0, 10)}</span>}
        <span className={`tone ${a.tone <= -5 ? "vneg" : a.tone < 0 ? "neg" : "pos"}`} title="GDELT document tone (−100…+100, usually −10…+10)">
          tone {a.tone > 0 ? "+" : ""}{a.tone}
        </span>
      </div>

      {a.loc && (
        <div className="row">
          <span className="k">Location</span>
          <button className="link" onClick={() => onPlace(a.loc!.name)} title="Filter on this place">
            📍 {a.loc.name}
          </button>
          {![3, 4].includes(a.loc.type) && <span className="muted"> (country/region level)</span>}
        </div>
      )}
      {a.orgs.length > 0 && (
        <div className="row">
          <span className="k">Organisations</span>
          <span className="tags">
            {a.orgs.slice(0, open ? 10 : 5).map((o) => (
              <button key={o} className="tag" onClick={() => onOrg(o)} title="Search this organisation">{o}</button>
            ))}
          </span>
        </div>
      )}
      {counts.length > 0 && (
        <div className="row">
          <span className="k">Reported</span>
          <span>
            {counts.map((c, i) => (
              <span key={i} className="count-pill">{c.n.toLocaleString()} {c.object || ""} {COUNT_LABELS[c.type]}</span>
            ))}
          </span>
        </div>
      )}

      {open && (
        <div className="details">
          <div className="row"><span className="k">All places</span><span>{a.places.join(" · ") || "—"}</span></div>
          <div className="row"><span className="k">GDELT themes</span><span className="mono">{a.themes.join(", ")}</span></div>
          <div className="row"><span className="k">Times</span>
            <span>published {fmtUtc(a.t)}{a.pubExact ? "" : " (approx.)"} · seen {fmtUtc(a.seen)}</span></div>
          <div className="row"><span className="k">Feed</span><span>{a.feed === "en" ? "English" : "Translated"} · {langName(a.lang)}</span></div>
        </div>
      )}
      <button className="link small" onClick={() => setOpen(!open)}>{open ? "Less" : "More details"}</button>
    </article>
  );
}
