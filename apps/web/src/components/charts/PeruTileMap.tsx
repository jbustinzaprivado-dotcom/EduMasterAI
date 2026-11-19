import { useState } from "react";

/**
 * Mapa de mosaicos (cartograma) del Perú: cada departamento es un cuadrado ubicado según su posición aproximada.
 * Evita depender de archivos geográficos pesados y da a cada región el mismo tamaño visual (§4.1, D30).
 */
const TILES: Record<string, [number, number]> = {
  Tumbes: [1, 0], Piura: [0, 1], Amazonas: [2, 1], Loreto: [4, 1], Lambayeque: [0, 2], Cajamarca: [1, 2],
  "San Martín": [3, 2], "La Libertad": [1, 3], Ucayali: [4, 3], Áncash: [1, 4], Huánuco: [2, 4], Pasco: [2, 5],
  Callao: [0, 6], Lima: [1, 6], Junín: [2, 6], "Madre de Dios": [5, 6], Ica: [1, 7], Huancavelica: [2, 7],
  Cusco: [4, 7], Ayacucho: [2, 8], Apurímac: [3, 8], Puno: [4, 8], Arequipa: [2, 9], Moquegua: [3, 9], Tacna: [3, 10],
};

const ABBR: Record<string, string> = {
  Tumbes: "TUM", Piura: "PIU", Amazonas: "AMA", Loreto: "LOR", Lambayeque: "LAM", Cajamarca: "CAJ",
  "San Martín": "SAM", "La Libertad": "LAL", Ucayali: "UCA", Áncash: "ANC", Huánuco: "HUC", Pasco: "PAS",
  Callao: "CAL", Lima: "LIM", Junín: "JUN", "Madre de Dios": "MDD", Ica: "ICA", Huancavelica: "HUV",
  Cusco: "CUS", Ayacucho: "AYA", Apurímac: "APU", Puno: "PUN", Arequipa: "ARE", Moquegua: "MOQ", Tacna: "TAC",
};

export interface RegionValue {
  region: string;
  students: number;
  avg_progress: number;
  completion_rate: number;
}

// Escala secuencial azul → cian según el progreso promedio (0-100 %).
function color(p: number): string {
  const from = [13, 43, 82];
  const to = [32, 200, 245];
  const t = Math.max(0, Math.min(1, p));
  return `rgb(${from.map((f, i) => Math.round(f + (to[i]! - f) * t)).join(" ")})`;
}

export function PeruTileMap({ data }: { data: RegionValue[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const byRegion = new Map(data.map((d) => [d.region, d]));
  const size = 34;
  const gap = 4;
  const active = hover ? byRegion.get(hover) : undefined;

  return (
    <div className="flex flex-col items-center gap-3">
      <svg viewBox={`0 0 ${6 * (size + gap)} ${11 * (size + gap)}`} className="w-full max-w-52" role="img"
        aria-label={data.length ? data.map((d) => `${d.region}: ${d.students} estudiantes, progreso ${Math.round(d.avg_progress * 100)} %`).join("; ") : "Sin regiones con datos suficientes"}>
        {Object.entries(TILES).map(([name, [c, r]]) => {
          const d = byRegion.get(name);
          return (
            <g key={name} onMouseEnter={() => setHover(name)} onMouseLeave={() => setHover(null)}>
              <rect x={c * (size + gap)} y={r * (size + gap)} width={size} height={size} rx={6}
                fill={d ? color(d.avg_progress) : "rgb(10 31 61)"} stroke={hover === name ? "#eaf2ff" : "rgb(32 140 245 / 0.25)"}
                strokeWidth={hover === name ? 1.5 : 1} />
              <text x={c * (size + gap) + size / 2} y={r * (size + gap) + size / 2 + 3.5} textAnchor="middle" fontSize={9}
                fill={d ? "#06152b" : "#5d7396"} fontWeight={d ? 700 : 500}>{ABBR[name]}</text>
              <title>{d ? `${name}: ${d.students} estudiantes · progreso ${Math.round(d.avg_progress * 100)} %` : `${name}: sin datos o grupo < 3`}</title>
            </g>
          );
        })}
      </svg>
      <div className="w-full text-xs">
        <div className="mb-2 h-1.5 w-full rounded-full" style={{ background: `linear-gradient(90deg, ${color(0)}, ${color(1)})` }} />
        <div className="mb-3 flex justify-between text-muted"><span>0 %</span><span>progreso promedio</span><span>100 %</span></div>
        {active ? (
          <p className="mb-2 text-sm"><b>{active.region}</b> · {active.students} estudiantes · {Math.round(active.avg_progress * 100)} % de progreso · {Math.round(active.completion_rate * 100)} % completaron</p>
        ) : null}
        <ul className="space-y-1">
          {data.map((d) => (
            <li key={d.region} className="flex justify-between gap-2">
              <span>{d.region}</span>
              <span className="text-muted">{d.students} est. · {Math.round(d.avg_progress * 100)} %</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
