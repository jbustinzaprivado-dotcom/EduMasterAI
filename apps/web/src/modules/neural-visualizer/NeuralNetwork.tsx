import { useQuery } from "@tanstack/react-query";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../lib/api";
import { Badge, Button, ErrorState, Skeleton, cx } from "../../components/ui";

export interface Layer {
  id: string;
  name: string;
  role: "input" | "projection" | "hidden" | "temporal" | "fusion" | "output";
  display_nodes: number;
  units: string;
  operation: string;
  dimension: string;
  detail: string[];
}

export interface Architecture {
  model_name: string;
  status: string;
  status_label: string;
  version: string | null;
  dataset: string | null;
  source: string;
  note: string;
  layers: Layer[];
}

export function useArchitecture() {
  return useQuery({ queryKey: ["ml", "architecture"], queryFn: () => api<Architecture>("/ml/architecture") });
}

// Colores por tipo de capa (§5.3).
const ROLE_COLOR: Record<Layer["role"], string> = {
  input: "#20c8f5",
  projection: "#6cb8ff",
  hidden: "#087fe5",
  temporal: "#8b4dff",
  fusion: "#087fe5",
  output: "#00bfa6",
};

const W = 640;
const H = 300;
const PAD_X = 60;
const PAD_Y = 34;

interface Pulse {
  from: [number, number];
  to: [number, number];
  layer: number; // índice de la capa de origen
  t: number; // avance 0..1
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Visualizador de la arquitectura (§4.10, §5.3, §5.4).
 * - La topología viene de la API, no está dibujada a mano.
 * - Sin modelo entrenado no hay animación "en vivo": solo una SIMULACIÓN DEMO que el usuario inicia,
 *   rotulada como tal, con pausa, reinicio, velocidad y respeto a prefers-reduced-motion.
 * - Los pulsos recorren conexiones reales del grafo, de izquierda a derecha (propagación hacia delante).
 */
export function NeuralNetwork({ arch, compact = false }: { arch: Architecture; compact?: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [, setFrame] = useState(0);
  const pulses = useRef<Pulse[]>([]);
  const reduced = useMemo(prefersReducedMotion, []);

  const nodes = useMemo(() => {
    const cols = arch.layers.length;
    return arch.layers.map((layer, i) => {
      const x = PAD_X + (i * (W - 2 * PAD_X)) / Math.max(cols - 1, 1);
      const n = layer.display_nodes;
      const span = Math.min(H - 2 * PAD_Y, n * 34);
      return Array.from({ length: n }, (_, j) => {
        const y = H / 2 - span / 2 + (n === 1 ? span / 2 : (j * span) / (n - 1));
        return [x, y] as [number, number];
      });
    });
  }, [arch]);

  useEffect(() => {
    if (!running) return;
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1) * speed;
      last = now;
      acc += dt;
      // Nuevos pulsos salen de la capa de entrada.
      if (acc > 0.18) {
        acc = 0;
        const src = nodes[0]!;
        const dst = nodes[1]!;
        pulses.current.push({ from: src[Math.floor(Math.random() * src.length)]!, to: dst[Math.floor(Math.random() * dst.length)]!, layer: 0, t: 0 });
      }
      const next: Pulse[] = [];
      for (const p of pulses.current) {
        p.t += dt * 1.4;
        if (p.t < 1) next.push(p);
        else if (p.layer + 2 < nodes.length) {
          const dst = nodes[p.layer + 2]!;
          next.push({ from: p.to, to: dst[Math.floor(Math.random() * dst.length)]!, layer: p.layer + 1, t: 0 });
        }
      }
      pulses.current = next.slice(-90);
      setFrame((f) => (f + 1) % 1_000_000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf); // se cancela al pausar o desmontar
  }, [running, speed, nodes]);

  const reset = () => {
    pulses.current = [];
    setRunning(false);
    setFrame(0);
  };

  const selectedLayer = arch.layers.find((l) => l.id === selected);
  const activeLayers = new Set(pulses.current.map((p) => p.layer));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="violet">{arch.status_label}</Badge>
        {running && <Badge tone="warning">SIMULACIÓN DEMO · no es un modelo en ejecución</Badge>}
        <div className="ml-auto flex items-center gap-2">
          {reduced ? (
            <span className="text-[11px] text-muted">Animación desactivada (movimiento reducido)</span>
          ) : (
            <>
              <Button variant="ghost" icon={running ? Pause : Play} onClick={() => setRunning((v) => !v)}
                className="px-2.5 py-1.5 text-xs">
                {running ? "Pausar" : "Simular"}
              </Button>
              <Button variant="ghost" icon={RotateCcw} onClick={reset} className="px-2.5 py-1.5 text-xs" aria-label="Reiniciar" />
              <label className="sr-only" htmlFor="nn-speed">Velocidad</label>
              <select id="nn-speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))}
                className="field w-auto px-2 py-1 text-xs">
                <option value={0.5}>0.5×</option>
                <option value={1}>1×</option>
                <option value={2}>2×</option>
              </select>
            </>
          )}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Arquitectura ${arch.model_name}`}
        className={cx("w-full rounded-xl bg-[radial-gradient(ellipse_at_center,rgb(8_127_229/0.12),transparent_70%)]",
          compact ? "max-h-64" : "max-h-[380px]")}>
        {/* Conexiones */}
        {nodes.slice(0, -1).map((col, i) =>
          col.flatMap(([x1, y1], a) =>
            nodes[i + 1]!.map(([x2, y2], b) => (
              <line key={`${i}-${a}-${b}`} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={ROLE_COLOR[arch.layers[i + 1]!.role]}
                strokeOpacity={running && activeLayers.has(i) ? 0.32 : 0.14} strokeWidth={0.8} />
            )),
          ),
        )}
        {/* Pulsos de la simulación */}
        {pulses.current.map((p, k) => (
          <circle key={k} cx={p.from[0] + (p.to[0] - p.from[0]) * p.t} cy={p.from[1] + (p.to[1] - p.from[1]) * p.t}
            r={2.6} fill="#9fe8ff" style={{ filter: "drop-shadow(0 0 4px #20c8f5)" }} />
        ))}
        {/* Nodos y rótulos de capa */}
        {arch.layers.map((layer, i) => {
          const isSel = selected === layer.id;
          const color = ROLE_COLOR[layer.role];
          return (
            <g key={layer.id} className="cursor-pointer" onClick={() => setSelected(isSel ? null : layer.id)}
              role="button" tabIndex={0} aria-label={`Capa ${layer.name}`} aria-pressed={isSel}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelected(isSel ? null : layer.id)}>
              {nodes[i]!.map(([x, y], j) => (
                <circle key={j} cx={x} cy={y} r={isSel ? 8 : 6.5} fill="#06152b" stroke={color} strokeWidth={isSel ? 2.6 : 1.8}
                  style={{ filter: `drop-shadow(0 0 ${isSel ? 8 : 4}px ${color})` }} />
              ))}
              <text x={nodes[i]![0]![0]} y={H - 8} textAnchor="middle" fontSize={11} fill={isSel ? "#eaf2ff" : "#8ea3c2"}>
                {layer.name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Inspector de capa (§4.10) */}
      <div className="rounded-xl border border-line bg-bg/40 p-3 text-xs">
        {selectedLayer ? (
          <div className="grid gap-2 sm:grid-cols-[1fr_1.2fr]">
            <div className="space-y-1">
              <p className="text-sm font-semibold" style={{ color: ROLE_COLOR[selectedLayer.role] }}>{selectedLayer.name}</p>
              <p><span className="text-muted">Operación:</span> {selectedLayer.operation}</p>
              <p><span className="text-muted">Unidades:</span> {selectedLayer.units}</p>
              <p><span className="text-muted">Dimensión:</span> <code className="text-cyan">{selectedLayer.dimension}</code></p>
            </div>
            <ul className="list-inside list-disc space-y-0.5 text-muted">
              {selectedLayer.detail.map((d) => <li key={d}><span className="text-text/90">{d}</span></li>)}
            </ul>
          </div>
        ) : (
          <p className="text-muted">Selecciona una capa para ver su operación, unidades y dimensión tensorial.</p>
        )}
      </div>
    </div>
  );
}

/** Panel de estado del modelo (§4.10): sin entrenamiento, los valores aparecen como "—". */
export function ModelStatus({ arch }: { arch: Architecture }) {
  const rows: [string, string][] = [
    ["Modelo", arch.model_name],
    ["Versión", arch.version ?? "—"],
    ["Dataset", arch.dataset ?? "—"],
    ["Época / loss", "—"],
    ["Métrica de validación", "—"],
    ["Latencia de inferencia", "—"],
    ["Fuente", arch.source],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="truncate text-text">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function NeuralNetworkLoader({ compact }: { compact?: boolean }) {
  const query = useArchitecture();
  if (query.isPending) return <Skeleton className="h-64" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <NeuralNetwork arch={query.data} compact={compact} />;
}
