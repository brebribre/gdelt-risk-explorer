export type RiskType = { code: string; category: string; label: string; gdeltThemes: string[] };
export type Category = { code: string; label: string };

export type Meta = {
  total: number;
  from: string;
  to: string;
  feeds: Record<string, number>;
  batches: Record<string, number>;
  scanned: number;
  categories: Category[];
  riskTypes: RiskType[];
};

export type Article = {
  id: number;
  t: string;
  seen: string;
  pubExact: boolean;
  feed: "en" | "translated";
  src: string;
  url: string;
  title: string;
  lang: string;
  tone: number;
  loc: { name: string; type: number; cc: string; country: string; lat: number; lon: number } | null;
  places: string[];
  orgs: string[];
  counts: { type: string; n: number; object: string }[];
  risks: string[];
  themes: string[];
};

export type Point = { name: string; country: string; lat: number; lon: number; n: number; precise: number };

export type SearchResult = {
  total: number;
  limit: number;
  offset: number;
  items: Article[];
  timeline: { hour: string; n: number }[];
  points: Point[];
  facets: {
    risks: { code: string; n: number }[];
    countries: { cc: string; name: string; n: number }[];
    langs: { code: string; n: number }[];
    sources: { src: string; n: number }[];
  };
};

export type Filters = {
  q: string;
  risks: string[];
  countries: string[];
  countryMode: "primary" | "any";
  langs: string[];
  feed: "" | "en" | "translated";
  from: string;
  to: string;
  toneMax: string;
  src: string;
  place: string;
  preciseLoc: boolean;
  sort: "new" | "old" | "tone";
};

export const EMPTY_FILTERS: Filters = {
  q: "", risks: [], countries: [], countryMode: "primary", langs: [], feed: "", from: "", to: "",
  toneMax: "", src: "", place: "", preciseLoc: false, sort: "new",
};

const LIST_KEYS = ["risks", "countries", "langs"] as const;

export function filtersToParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) {
    if (Array.isArray(v)) {
      if (v.length) p.set(k, v.join(","));
    } else if (typeof v === "boolean") {
      if (v) p.set(k, "1");
    } else if (v !== "" && v !== EMPTY_FILTERS[k as keyof Filters]) {
      p.set(k, v);
    }
  }
  return p;
}

export function paramsToFilters(p: URLSearchParams): Filters {
  const f: Filters = { ...EMPTY_FILTERS };
  for (const key of Object.keys(EMPTY_FILTERS) as (keyof Filters)[]) {
    const v = p.get(key);
    if (v === null) continue;
    if ((LIST_KEYS as readonly string[]).includes(key)) (f as any)[key] = v.split(",").filter(Boolean);
    else if (key === "preciseLoc") f.preciseLoc = v === "1";
    else (f as any)[key] = v;
  }
  return f;
}

/** Query string for the API (snake_case names the Python server expects). */
export function apiParams(f: Filters, offset: number, limit = 50): string {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.risks.length) p.set("risks", f.risks.join(","));
  if (f.countries.length) p.set("countries", f.countries.join(","));
  if (f.countryMode === "any") p.set("country_mode", "any");
  if (f.langs.length) p.set("langs", f.langs.join(","));
  if (f.feed) p.set("feed", f.feed);
  if (f.from) p.set("from", f.from);
  if (f.to) p.set("to", f.to);
  if (f.toneMax) p.set("tone_max", f.toneMax);
  if (f.src.trim()) p.set("src", f.src.trim());
  if (f.place) p.set("place", f.place);
  if (f.preciseLoc) p.set("precise_loc", "1");
  p.set("sort", f.sort);
  p.set("offset", String(offset));
  p.set("limit", String(limit));
  return p.toString();
}

export const CATEGORY_COLORS: Record<string, string> = {
  natural: "#0f7b8a",
  industrial: "#d1495b",
  labour: "#e07a1f",
  operations: "#8a6d0b",
  logistics: "#3b6fd1",
  geopolitical: "#7b4fd1",
  financial: "#2e8b57",
  cyber: "#c2189b",
  esg: "#5c7a1f",
  health: "#a0522d",
};

const langNames = (() => {
  try {
    return new Intl.DisplayNames(["en"], { type: "language" });
  } catch {
    return null;
  }
})();

// GDELT uses ISO 639-2 codes; a few bibliographic codes need mapping before Intl understands them.
const LANG_ALIASES: Record<string, string> = { fre: "fra", ger: "deu", chi: "zho", dut: "nld", per: "fas", cze: "ces", gre: "ell", rum: "ron", slo: "slk", alb: "sqi", arm: "hye", baq: "eus", bur: "mya", geo: "kat", ice: "isl", mac: "mkd", mao: "mri", may: "msa", tib: "bod", wel: "cym" };

export function langName(code: string): string {
  if (code === "eng") return "English";
  try {
    const name = langNames?.of(LANG_ALIASES[code] ?? code);
    return name && name !== code ? name : code;
  } catch {
    return code;
  }
}

export function timeAgo(iso: string, now: number): string {
  const mins = Math.round((now - Date.parse(iso)) / 60000);
  if (mins < 60) return `${Math.max(mins, 0)}m ago`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function fmtUtc(iso: string): string {
  return iso.slice(0, 16).replace("T", " ") + " UTC";
}

export const fmtNum = (n: number) => n.toLocaleString("en-US");
