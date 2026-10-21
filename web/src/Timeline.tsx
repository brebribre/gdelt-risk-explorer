import { useMemo, useState } from "react";
import { Meta, fmtNum } from "./lib";

type Props = {
  meta: Meta | null;
  data: { hour: string; n: number }[];
  from: string;
  to: string;
  onSelect: (from: string, to: string) => void;
};

const H = 90;

export default function Timeline({ meta, data, from, to, onSelect }: Props) {
  const [drag, setDrag] = useState<{ a: number; b: number } | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  // One bucket per hour across the ingestion window, zero-filled
  const buckets = useMemo(() => {
    if (!meta) return [];
    const counts = new Map(data.map((d) => [d.hour, d.n]));
    const out: { hour: string; n: number }[] = [];
    const start = Date.parse(meta.from.slice(0, 13) + ":00:00Z");
    const end = Date.parse(meta.to.slice(0, 13) + ":00:00Z");
    for (let t = start; t <= end; t += 3600000) {
      const hour = new Date(t).toISOString().slice(0, 13);
      out.push({ hour, n: counts.get(hour) ?? 0 });
    }
    return out;
  }, [meta, data]);

  if (!buckets.length) return <div className="timeline" style={{ height: H }} />;

  const max = Math.max(1, ...buckets.map((b) => b.n));
  const w = 100 / buckets.length;
  const inSelected = (hour: string) =>
    (!from || hour + ":59:59Z" >= from) && (!to || hour + ":00:00Z" <= to) && (from || to);
  const inDrag = (i: number) => drag && i >= Math.min(drag.a, drag.b) && i <= Math.max(drag.a, drag.b);

  const finish = () => {
    if (!drag) return;
    const a = buckets[Math.min(drag.a, drag.b)].hour;
    const b = buckets[Math.max(drag.a, drag.b)].hour;
    onSelect(`${a}:00:00Z`, `${b}:59:59Z`);
    setDrag(null);
  };

  const tip = hover !== null ? buckets[hover] : null;
  const days = buckets.map((b, i) => ({ i, b })).filter(({ b }) => b.hour.endsWith("T00"));

  return (
    <div className="timeline" onMouseLeave={() => { setHover(null); setDrag(null); }}>
      <svg viewBox={`0 0 100 ${H}`} preserveAspectRatio="none" width="100%" height={H} onMouseUp={finish}>
        {buckets.map((b, i) => {
          const h = (b.n / max) * (H - 4);
          const cls = inDrag(i) ? "bar drag" : inSelected(b.hour) ? "bar sel" : (from || to) ? "bar dim" : "bar";
          return (
            <g key={b.hour}
              onMouseDown={() => setDrag({ a: i, b: i })}
              onMouseEnter={() => { setHover(i); if (drag) setDrag({ ...drag, b: i }); }}>
              <rect x={i * w} y={0} width={w} height={H} fill="transparent" />
              <rect className={cls} x={i * w + w * 0.1} y={H - h} width={w * 0.8} height={h} />
            </g>
          );
        })}
        {days.map(({ i }) => (
          <line key={i} x1={i * w} x2={i * w} y1={0} y2={H} className="dayline" vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className="axis">
        {days.map(({ i, b }) => (
          <span key={i} style={{ left: `${i * w}%` }}>{b.hour.slice(5, 10)}</span>
        ))}
      </div>
      {tip && (
        <div className="tip" style={{ left: `${Math.min(Math.max((hover! + 0.5) * w, 6), 94)}%` }}>
          {tip.hour.replace("T", " ")}:00 UTC · {fmtNum(tip.n)}
        </div>
      )}
    </div>
  );
}
