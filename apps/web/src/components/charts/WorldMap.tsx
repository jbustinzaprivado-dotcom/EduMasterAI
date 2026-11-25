import { useId, useState } from "react";
import type { RegionValue } from "./PeruTileMap";
import { WORLD } from "./worldDots";

/**
 * Mapa mundial de puntos (imagen de referencia del manual, D47). Es demostrativo: hoy todos los estudiantes DEMO
 * están en el Perú, así que solo brilla Sudamérica. Usa los mismos datos agregados del mapa del Perú (k-anonimato
 * ya aplicado en la API): cada departamento visible es un punto en su capital.
 *
 * Rendimiento: los 2 456 puntos de tierra son UN solo <path> calculado una vez al cargar el módulo.
 */
const CELL = 10;
const W = WORLD.cols * CELL;
const H = WORLD.rows * CELL;

const project = (lon: number, lat: number): [number, number] => [
  ((lon + 180) / WORLD.step) * CELL,
  ((WORLD.latTop - lat) / WORLD.step) * CELL,
];

const LAND_PATH = (() => {
  const bytes = Uint8Array.from(atob(WORLD.bits), (c) => c.charCodeAt(0));
  const r = 2.6;
  let d = "";
  for (let i = 0; i < WORLD.cols * WORLD.rows; i++) {
    if (!(bytes[i >> 3]! & (1 << (7 - (i & 7))))) continue;
    const x = (i % WORLD.cols) * CELL + CELL / 2;
    const y = Math.floor(i / WORLD.cols) * CELL + CELL / 2;
    d += `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
  }
  return d;
})();

// Capital de cada departamento (lat, lon) para ubicar los puntos del Perú.
const CAPITALS: Record<string, [number, number]> = {
  Tumbes: [-3.57, -80.45], Piura: [-5.19, -80.63], Amazonas: [-6.23, -77.87], Loreto: [-3.75, -73.25],
  Lambayeque: [-6.77, -79.84], Cajamarca: [-7.16, -78.51], "San Martín": [-6.03, -76.97], "La Libertad": [-8.11, -79.03],
  Ucayali: [-8.38, -74.55], Áncash: [-9.53, -77.53], Huánuco: [-9.93, -76.24], Pasco: [-10.68, -76.26],
  Callao: [-12.05, -77.12], Lima: [-12.05, -77.04], Junín: [-12.07, -75.21], "Madre de Dios": [-12.59, -69.19],
  Ica: [-14.07, -75.73], Huancavelica: [-12.79, -74.97], Cusco: [-13.53, -71.97], Ayacucho: [-13.16, -74.22],
  Apurímac: [-13.64, -72.88], Puno: [-15.84, -70.02], Arequipa: [-16.41, -71.54], Moquegua: [-17.19, -70.94],
  Tacna: [-18.01, -70.25],
};

// Cifras por continente, como en la referencia (debajo del mapa para no taparlo en un panel angosto).
const CONTINENTS: { name: string; peru?: boolean }[] = [
  { name: "América del Norte" }, { name: "Europa" }, { name: "Asia" },
  { name: "América del Sur", peru: true }, { name: "África" }, { name: "Oceanía" },
];

export function WorldMap({ regions, total }: { regions: RegionValue[]; total: number }) {
  const uid = useId().replace(/:/g, "");
  const [hover, setHover] = useState<RegionValue | null>(null);
  const [px, py] = project(-75, -9.5); // centro del Perú
  const points = regions.filter((r) => CAPITALS[r.region]);
  return (
    <div className="flex flex-col gap-2">
      <div>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" className="w-full"
          aria-label={`Mapa mundial: ${total} estudiantes registrados, todos en el Perú (América del Sur)`}>
          <defs>
            <radialGradient id={`glow-${uid}`}>
              <stop offset="0%" stopColor="#20c8f5" stopOpacity="0.75" />
              <stop offset="45%" stopColor="#087fe5" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#087fe5" stopOpacity="0" />
            </radialGradient>
          </defs>
          <path d={LAND_PATH} fill="#3a7bd5" fillOpacity={0.5} />
          {total > 0 && (
            <>
              <circle cx={px} cy={py} r={150} fill={`url(#glow-${uid})`} />
              <circle cx={px} cy={py} r={34} fill="none" stroke="#20c8f5" strokeWidth={3} className="world-pulse" />
            </>
          )}
          {points.map((r) => {
            const [lat, lon] = CAPITALS[r.region]!;
            const [x, y] = project(lon, lat);
            return (
              <circle key={r.region} cx={x} cy={y} r={hover?.region === r.region ? 12 : 9} fill="#9fe8ff"
                stroke="#06152b" strokeWidth={2} className="cursor-pointer"
                onMouseEnter={() => setHover(r)} onMouseLeave={() => setHover(null)}>
                <title>{`${r.region}: ${r.students} estudiantes · ${Math.round(r.avg_progress * 100)} % de progreso`}</title>
              </circle>
            );
          })}
        </svg>
      </div>
      <ul className="grid grid-cols-3 gap-1.5" aria-label="Estudiantes por continente">
        {CONTINENTS.map((c) => {
          const n = c.peru ? total : 0;
          return (
            <li key={c.name} className={`rounded-md border px-2 py-1 text-[10px] leading-tight ${
              n ? "border-cyan/50 bg-primary/10 text-text shadow-[0_0_12px_rgb(32_200_245/0.3)]" : "border-line/60 text-muted"}`}>
              <p className="truncate">{c.name}</p>
              <p className={`text-sm font-semibold ${n ? "text-cyan" : ""}`}>{n}</p>
            </li>
          );
        })}
      </ul>
      <p className="text-[11px] text-muted">
        {hover
          ? `${hover.region}: ${hover.students} estudiantes · progreso promedio ${Math.round(hover.avg_progress * 100)} %`
          : `Perú · ${total} estudiantes registrados con matrícula. Datos DEMO: por ahora todos están en el Perú.`}
      </p>
    </div>
  );
}
