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
  metrics?: { roc_auc: number; pr_auc: number; brier: number; threshold: number } | null;
  last_run?: { at: string; count: number; latency_ms: number } | null;
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
const REVEAL_MS = 260; // una capa nueva cada 0,26 s al aparecer (D48)

type Point = [number, number];

interface Pulse {
  from: Point;
  to: Point;
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Pulsos de la simulación, por capas (D48): una onda de pocos pulsos viaja de la capa i a la i+1; al llegar sale la
 * siguiente, hasta la salida, y luego vuelve a empezar. Este componente es el ÚNICO que se redibuja en cada cuadro:
 * la red (conexiones y nodos) queda fija y memorizada.
 */
function Pulses({ nodes, speed, onLayer }: { nodes: Point[][]; speed: number; onLayer: (layer: number) => void }) {
  const [, setFrame] = useState(0);
  const wave = useRef<{ layer: number; t: number; pulses: Pulse[]; rest: number }>({ layer: -1, t: 0, pulses: [], rest: 0 });

  useEffect(() => {
    const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)]!;
    const launch = (layer: number) => {
      const src = nodes[layer]!;
      const dst = nodes[layer + 1]!;
      const count = Math.min(6, Math.max(src.length, dst.length));
      wave.current = { layer, t: 0, rest: 0, pulses: Array.from({ length: count }, () => ({ from: pick(src), to: pick(dst) })) };
      onLayer(layer);
    };
    launch(0);
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1) * speed;
      last = now;
      const w = wave.current;
      if (w.rest > 0) {
        w.rest -= dt;
        if (w.rest <= 0) launch(0);
      } else {
        w.t += dt * 1.6;
        if (w.t >= 1) {
          if (w.layer + 2 < nodes.length) launch(w.layer + 1);
          else { w.pulses = []; w.rest = 0.6; onLayer(-1); } // terminó la red: pausa breve y otra onda
        }
      }
      setFrame((f) => (f + 1) % 1_000_000);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); onLayer(-1); }; // se detiene al pausar o desmontar
  }, [nodes, speed, onLayer]);

  const { t, pulses } = wave.current;
  return (
    <g pointerEvents="none">
      {pulses.map((p, k) => (
        <circle key={k} cx={p.from[0] + (p.to[0] - p.from[0]) * Math.min(t, 1)} cy={p.from[1] + (p.to[1] - p.from[1]) * Math.min(t, 1)}
          r={2.8} fill="#9fe8ff" />
      ))}
    </g>
  );
}

/**
 * Visualizador de la arquitectura (§4.10, §5.3, §5.4).
 * - La topología viene de la API, no está dibujada a mano.
 * - Al cargar, la red se arma capa por capa (D48); con movimiento reducido aparece completa.
 * - Sin modelo entrenado no hay animación "en vivo": solo una SIMULACIÓN DEMO que el usuario inicia,
 *   rotulada como tal, con pausa, reinicio, velocidad y respeto a prefers-reduced-motion.
 * - La simulación recorre la red una capa a la vez, de izquierda a derecha (propagación hacia delante).
 */
export const INPUT_LABELS = ["Días activos", "Sesiones", "Avance", "Ritmo", "Notas", "Tendencia", "Entregas tardías", "Inactividad"];
export const OUTPUT_LABELS = ["Finalización", "Dominio", "Riesgo de abandono", "Recomendaciones"];

export function NeuralNetwork({ arch, compact = false, labeled = false }: { arch: Architecture; compact?: boolean; labeled?: boolean }) {
  const padL = labeled ? 112 : PAD_X;
  const padR = labeled ? 120 : PAD_X;
  const reduced = useMemo(prefersReducedMotion, []);
  const total = arch.layers.length;
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [activeLayer, setActiveLayer] = useState(-1);
  const [revealed, setRevealed] = useState(reduced ? total : 1);

  const nodes = useMemo<Point[][]>(() => {
    const cols = arch.layers.length;
    return arch.layers.map((layer, i) => {
      const x = padL + (i * (W - padL - padR)) / Math.max(cols - 1, 1);
      const n = layer.display_nodes;
      const span = Math.min(H - 2 * PAD_Y, n * 34);
      return Array.from({ length: n }, (_, j) => {
        const y = H / 2 - span / 2 + (n === 1 ? span / 2 : (j * span) / (n - 1));
        return [x, y] as Point;
      });
    });
  }, [arch, padL, padR]);

  // Aparición progresiva: una capa más cada REVEAL_MS hasta completar la red.
  useEffect(() => {
    if (revealed >= total) return;
    const id = window.setTimeout(() => setRevealed((r) => r + 1), REVEAL_MS);
    return () => window.clearTimeout(id);
  }, [revealed, total]);

  // Conexiones: UN trazo por par de capas (en lugar de una línea SVG por conexión).
  const links = useMemo(() => nodes.slice(0, -1).map((col, i) =>
    col.flatMap(([x1, y1]) => nodes[i + 1]!.map(([x2, y2]) => `M${x1} ${y1}L${x2} ${y2}`)).join("")), [nodes]);

  const start = () => { setRevealed(total); setRunning((v) => !v); };
  const reset = () => { setRunning(false); setActiveLayer(-1); };
  const selectedLayer = arch.layers.find((l) => l.id === selected);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={arch.status === "design" ? "violet" : "teal"}>{arch.status_label}</Badge>
        {running && (arch.status === "design"
          ? <Badge tone="warning">SIMULACIÓN DEMO · no es un modelo en ejecución</Badge>
          : <Badge tone="cyan">Ilustración del recorrido de la inferencia</Badge>)}
        <div className="ml-auto flex items-center gap-2">
          {reduced ? (
            <span className="text-[11px] text-muted">Animación desactivada (movimiento reducido)</span>
          ) : (
            <>
              <Button variant="ghost" icon={running ? Pause : Play} onClick={start} className="px-2.5 py-1.5 text-xs">
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
        {/* Conexiones de cada par de capas: aparecen cuando aparece la capa de destino */}
        {links.map((d, i) => i + 1 < revealed && (
          <path key={`l-${i}`} d={d} fill="none" stroke={ROLE_COLOR[arch.layers[i + 1]!.role]} strokeWidth={0.8}
            strokeOpacity={activeLayer === i ? 0.42 : 0.14} className={reduced ? undefined : "nn-layer-in"} />
        ))}
        {/* Etiquetas: variables de entrada (izquierda) y salidas del modelo (derecha) */}
        {labeled && nodes[0]!.map(([x, y], j) => (
          <text key={`in-${j}`} x={x - 12} y={y + 3.5} textAnchor="end" fontSize={10.5} fill="#9fb4d4">{INPUT_LABELS[j]}</text>
        ))}
        {labeled && revealed >= total && nodes[total - 1]!.map(([x, y], j) => (
          <text key={`out-${j}`} x={x + 12} y={y + 3.5} fontSize={10.5} className={reduced ? undefined : "nn-layer-in"}
            fill={j === 2 && arch.status !== "design" ? "#00bfa6" : "#9fb4d4"}>{OUTPUT_LABELS[j]}</text>
        ))}
        {/* Nodos y rótulos de capa */}
        {arch.layers.map((layer, i) => {
          if (i >= revealed) return null;
          const isSel = selected === layer.id;
          const lit = isSel || activeLayer === i || activeLayer === i - 1;
          const color = ROLE_COLOR[layer.role];
          return (
            <g key={layer.id} className={cx("cursor-pointer", !reduced && "nn-layer-in")}
              onClick={() => setSelected(isSel ? null : layer.id)}
              role="button" tabIndex={0} aria-label={`Capa ${layer.name}`} aria-pressed={isSel}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelected(isSel ? null : layer.id)}>
              {nodes[i]!.map(([x, y], j) => (
                <g key={j}>
                  {/* Halo simple en lugar de un filtro drop-shadow por nodo (mucho más liviano) */}
                  <circle cx={x} cy={y} r={lit ? 12 : 10} fill={color} fillOpacity={lit ? 0.22 : 0.1} />
                  <circle cx={x} cy={y} r={isSel ? 8 : 6.5} fill="#06152b" stroke={color} strokeWidth={isSel ? 2.6 : 1.8} />
                </g>
              ))}
              <text x={nodes[i]![0]![0]} y={H - 8} textAnchor="middle" fontSize={11} fill={isSel ? "#eaf2ff" : "#8ea3c2"}>
                {layer.name}
              </text>
            </g>
          );
        })}
        {running && <Pulses nodes={nodes} speed={speed} onLayer={setActiveLayer} />}
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
  const m = arch.metrics;
  const rows: [string, string][] = [
    ["Modelo", arch.model_name],
    ["Versión", arch.version ?? "—"],
    ["Dataset", arch.dataset ?? "—"],
    ["ROC-AUC / PR-AUC (prueba)", m ? `${m.roc_auc.toFixed(3)} / ${m.pr_auc.toFixed(3)}` : "—"],
    ["Brier · umbral", m ? `${m.brier.toFixed(3)} · ${m.threshold}` : "—"],
    ["Última inferencia", arch.last_run ? `${arch.last_run.count} matrículas` : "—"],
    ["Latencia por matrícula", arch.last_run ? `${arch.last_run.latency_ms} ms` : "—"],
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
