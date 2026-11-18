import { useState } from "react";

/** Gráficos SVG livianos con leyenda, unidades y tooltip (§5.2). Sin librerías: cargan rápido en el túnel. */

export interface Series {
  key: string;
  label: string;
  unit: string;
  color: string;
  values: number[];
}

export function TrendChart({ labels, series, height = 200 }: { labels: string[]; series: Series[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640;
  const H = height;
  const pad = { l: 34, r: 12, t: 12, b: 26 };
  const n = labels.length;
  const x = (i: number) => pad.l + (n <= 1 ? 0 : (i * (W - pad.l - pad.r)) / (n - 1));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-4 text-xs text-muted" aria-hidden>
        {series.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded" style={{ background: s.color }} /> {s.label} ({s.unit})
          </span>
        ))}
      </div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
          aria-label={series.map((s) => `${s.label}: ${s.values.join(", ")} ${s.unit}`).join(". ")}
          onMouseLeave={() => setHover(null)}>
          {[0, 0.25, 0.5, 0.75, 1].map((f) => (
            <line key={f} x1={pad.l} x2={W - pad.r} y1={pad.t + f * (H - pad.t - pad.b)} y2={pad.t + f * (H - pad.t - pad.b)}
              stroke="rgb(32 140 245 / 0.12)" />
          ))}
          {series.map((s) => {
            const max = Math.max(1, ...s.values);
            const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
            const d = s.values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
            const area = `${d} L${x(n - 1)},${H - pad.b} L${x(0)},${H - pad.b} Z`;
            return (
              <g key={s.key}>
                <path d={area} fill={s.color} opacity={0.08} />
                <path d={d} fill="none" stroke={s.color} strokeWidth={2.2} style={{ filter: `drop-shadow(0 0 4px ${s.color})` }} />
                {s.values.map((v, i) => (
                  <circle key={i} cx={x(i)} cy={y(v)} r={hover === i ? 4.5 : 2.8} fill="#06152b" stroke={s.color} strokeWidth={2} />
                ))}
              </g>
            );
          })}
          {labels.map((l, i) => (
            <g key={l + i}>
              <text x={x(i)} y={H - 6} textAnchor="middle" fontSize={10.5} fill="#8ea3c2">{l}</text>
              <rect x={x(i) - (W - pad.l - pad.r) / (2 * Math.max(n - 1, 1))} y={0}
                width={(W - pad.l - pad.r) / Math.max(n - 1, 1)} height={H} fill="transparent"
                onMouseEnter={() => setHover(i)} />
            </g>
          ))}
        </svg>
        {hover !== null && (
          <div className="panel pointer-events-none absolute top-1 px-3 py-2 text-xs"
            style={{ left: `${Math.min(80, Math.max(0, (x(hover) / W) * 100 - 10))}%` }}>
            <p className="mb-1 font-semibold">{labels[hover]}</p>
            {series.map((s) => (
              <p key={s.key} style={{ color: s.color }}>{s.label}: {s.values[hover]} {s.unit}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export interface Slice {
  label: string;
  value: number;
  color: string;
}

export function Donut({ slices, center }: { slices: Slice[]; center: string }) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  const r = 52;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg viewBox="0 0 140 140" className="size-36 shrink-0" role="img"
        aria-label={slices.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        <circle cx={70} cy={70} r={r} fill="none" stroke="rgb(13 43 82)" strokeWidth={16} />
        {total > 0 && slices.map((s) => {
          const len = (s.value / total) * c;
          const el = (
            <circle key={s.label} cx={70} cy={70} r={r} fill="none" stroke={s.color} strokeWidth={16}
              strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)">
              <title>{`${s.label}: ${s.value} (${Math.round((100 * s.value) / total)} %)`}</title>
            </circle>
          );
          offset += len;
          return el;
        })}
        <text x={70} y={68} textAnchor="middle" fontSize={22} fontWeight={700} fill="#eaf2ff">{center}</text>
        <text x={70} y={86} textAnchor="middle" fontSize={10} fill="#8ea3c2">finalización</text>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: s.color }} />
            <span className="text-muted">{s.label}</span>
            <span className="ml-auto pl-3 font-semibold">{s.value}</span>
            <span className="w-10 text-right text-xs text-muted">{total ? Math.round((100 * s.value) / total) : 0} %</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ProgressBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className={className}>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-gradient-to-r from-primary to-cyan shadow-[0_0_8px_var(--color-cyan)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
