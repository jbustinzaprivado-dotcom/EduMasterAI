import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Badge, ErrorState, Skeleton, cx } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

/** Recorrido real de una predicción (D51): activaciones de la red publicada para una matrícula. */

interface TraceNode {
  index: number;
  label: string;
  value: number | null;
  intensity: number;
}

interface TraceLayer {
  id: "input" | "projection" | "temporal" | "fusion" | "heads";
  name: string;
  total: string;
  nodes: TraceNode[];
}

interface TraceEdge {
  source_layer: string;
  source: number;
  target_layer: string;
  target: number;
  strength: number;
  sign: 1 | -1;
}

export interface Trace {
  enrollment_id: string;
  student_name: string;
  course: string;
  model_version: string;
  computed_at: string;
  probability: number;
  threshold: number;
  risk_level: "alto" | "medio" | "bajo";
  factors: { feature: string; label: string; impact: number }[];
  layers: TraceLayer[];
  edges: TraceEdge[];
}

const COLOR: Record<TraceLayer["id"], string> = {
  input: "#20c8f5",
  projection: "#6cb8ff",
  temporal: "#8b4dff",
  fusion: "#087fe5",
  heads: "#00bfa6",
};
const UP = "#00bfa6";
const DOWN = "#ff5c8a";
const RISK_TONE = { alto: "danger", medio: "warning", bajo: "teal" } as const;

const W = 820;
const H = 330;
const PAD_L = 185; // cabe "Evaluaciones sin entregar 0.50"
const PAD_R = 185; // cabe "C · Riesgo de abandono · 80 %"
const PAD_Y = 34;
const REVEAL_MS = 420; // la señal avanza una capa cada 0,42 s

type Point = [number, number];
const key = (layer: string, index: number) => `${layer}:${index}`;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function fmt(value: number | null) {
  return value === null ? "sin entrenar" : value.toFixed(3);
}

export function useTrace(enrollmentId: string | null) {
  return useQuery({
    queryKey: ["ml", "trace", enrollmentId],
    queryFn: () => api<Trace>(`/ml/enrollments/${enrollmentId}/trace`),
    enabled: !!enrollmentId,
    staleTime: 60_000,
  });
}

export function TraceView({ enrollmentId }: { enrollmentId: string }) {
  const query = useTrace(enrollmentId);
  if (query.isPending) return <Skeleton className="h-80" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <TraceDiagram trace={query.data} />;
}

export function TraceDiagram({ trace }: { trace: Trace }) {
  const reduced = useMemo(prefersReducedMotion, []);
  const total = trace.layers.length;
  const [revealed, setRevealed] = useState(reduced ? total : 1);
  const [selected, setSelected] = useState<string | null>(null);

  // Cada traza nueva vuelve a recorrerse desde la entrada.
  useEffect(() => { setRevealed(reduced ? total : 1); setSelected(null); }, [trace, reduced, total]);
  useEffect(() => {
    if (revealed >= total) return;
    const id = window.setTimeout(() => setRevealed((r) => r + 1), REVEAL_MS);
    return () => window.clearTimeout(id);
  }, [revealed, total]);

  const layerIndex = useMemo(() => new Map(trace.layers.map((l, i) => [l.id as string, i])), [trace]);
  const pos = useMemo(() => {
    const map = new Map<string, Point>();
    trace.layers.forEach((layer, i) => {
      const x = PAD_L + (i * (W - PAD_L - PAD_R)) / (total - 1);
      const n = layer.nodes.length;
      const span = Math.min(H - 2 * PAD_Y - 14, n * 36);
      layer.nodes.forEach((node, j) => {
        const y = (H - 14) / 2 - span / 2 + (n === 1 ? span / 2 : (j * span) / (n - 1));
        map.set(key(layer.id, node.index), [x, y]);
      });
    });
    return map;
  }, [trace, total]);

  const labelOf = (layerId: string, index: number) =>
    trace.layers.find((l) => l.id === layerId)?.nodes.find((n) => n.index === index)?.label ?? "";
  const sel = selected ? (() => {
    const [layerId, idx] = selected.split(":");
    const layer = trace.layers.find((l) => l.id === layerId)!;
    const node = layer.nodes.find((n) => n.index === Number(idx))!;
    const incoming = trace.edges.filter((e) => e.target_layer === layerId && e.target === node.index)
      .sort((a, b) => b.strength - a.strength);
    const outgoing = trace.edges.filter((e) => e.source_layer === layerId && e.source === node.index)
      .sort((a, b) => b.strength - a.strength);
    return { layer, node, incoming, outgoing };
  })() : null;
  const linked = new Set(sel ? [...sel.incoming.map((e) => key(e.source_layer, e.source)),
    ...sel.outgoing.map((e) => key(e.target_layer, e.target))] : []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-text">{trace.student_name}</span>
        <span className="text-muted">{trace.course}</span>
        <Badge tone={RISK_TONE[trace.risk_level]}>
          Riesgo {trace.risk_level} · {Math.round(trace.probability * 100)} %
        </Badge>
        <Badge tone="cyan">Datos reales · modelo v{trace.model_version}</Badge>
        <span className="ml-auto text-muted">Calculado {formatDateTime(trace.computed_at)} con los datos actuales</span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img" data-testid="trace-svg"
        aria-label={`Recorrido de la predicción de ${trace.student_name}: ${Math.round(trace.probability * 100)} % de riesgo`}
        className="w-full rounded-xl bg-[radial-gradient(ellipse_at_center,rgb(0_191_166/0.08),transparent_70%)]">
        {/* Conexiones reales: grosor = cuánto aportó; verde sube la activación, rosado la baja */}
        {trace.edges.map((e, k) => {
          const target = layerIndex.get(e.target_layer)!;
          if (target >= revealed) return null;
          const [x1, y1] = pos.get(key(e.source_layer, e.source))!;
          const [x2, y2] = pos.get(key(e.target_layer, e.target))!;
          const mx = (x1 + x2) / 2;
          const onPath = !sel || selected === key(e.source_layer, e.source) || selected === key(e.target_layer, e.target);
          return (
            <path key={k} d={`M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`} fill="none"
              stroke={e.sign > 0 ? UP : DOWN} strokeWidth={0.6 + 2.6 * e.strength}
              strokeOpacity={onPath ? 0.2 + 0.65 * e.strength : 0.06} className={reduced ? undefined : "nn-layer-in"} />
          );
        })}
        {trace.layers.map((layer, i) => i < revealed && (
          <g key={layer.id} className={reduced ? undefined : "nn-layer-in"}>
            {layer.nodes.map((node) => {
              const k = key(layer.id, node.index);
              const [x, y] = pos.get(k)!;
              const isSel = selected === k;
              const dim = sel && !isSel && !linked.has(k);
              const planned = node.value === null;
              return (
                <g key={k} className="cursor-pointer" role="button" tabIndex={0} aria-pressed={isSel}
                  aria-label={`${layer.name}, ${node.label}: ${fmt(node.value)}`}
                  onClick={() => setSelected(isSel ? null : k)}
                  onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && setSelected(isSel ? null : k)}
                  opacity={dim ? 0.35 : 1}>
                  <title>{`${node.label} · ${fmt(node.value)}`}</title>
                  {!planned && <circle cx={x} cy={y} r={9 + 7 * node.intensity} fill={COLOR[layer.id]} fillOpacity={0.08 + 0.3 * node.intensity} />}
                  <circle cx={x} cy={y} r={isSel ? 8.5 : 7} fill={planned ? "#06152b" : COLOR[layer.id]}
                    fillOpacity={planned ? 1 : 0.15 + 0.8 * node.intensity}
                    stroke={planned ? "#4a5d7a" : COLOR[layer.id]} strokeWidth={isSel ? 2.6 : 1.6}
                    strokeDasharray={planned ? "3 3" : undefined} />
                </g>
              );
            })}
            <text x={pos.get(key(layer.id, layer.nodes[0]!.index))![0]} y={H - 8} textAnchor="middle" fontSize={11} fill="#8ea3c2">
              {layer.name}
            </text>
          </g>
        ))}
        {/* Variables de entrada con su valor real, y cabezas de salida con la probabilidad */}
        {trace.layers[0]!.nodes.map((node) => {
          const [x, y] = pos.get(key("input", node.index))!;
          return (
            <text key={`in-${node.index}`} x={x - 14} y={y + 3.5} textAnchor="end" fontSize={10.5} fill="#9fb4d4">
              {node.label} <tspan fill="#eaf2ff">{node.value?.toFixed(2)}</tspan>
            </text>
          );
        })}
        {revealed >= total && trace.layers[total - 1]!.nodes.map((node) => {
          const [x, y] = pos.get(key("heads", node.index))!;
          return (
            <text key={`out-${node.index}`} x={x + 14} y={y + 3.5} fontSize={10.5}
              fill={node.value === null ? "#6b7f9e" : "#00bfa6"} fontWeight={node.value === null ? 400 : 600}
              className={reduced ? undefined : "nn-layer-in"}>
              {node.label}{node.value !== null && ` · ${Math.round(node.value * 100)} %`}
            </text>
          );
        })}
      </svg>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-xl border border-line bg-bg/40 p-3">
          {sel ? (
            <div className="space-y-1.5">
              <p className="text-sm font-semibold" style={{ color: COLOR[sel.layer.id] }}>{sel.layer.name} · {sel.node.label}</p>
              <p><span className="text-muted">Activación real:</span> <code className="text-cyan">{fmt(sel.node.value)}</code></p>
              <p className="text-muted">
                {sel.layer.id === "heads" ? "Solo la cabeza C está entrenada; las otras 3 esperan datos reales."
                  : sel.layer.id === "input" ? `Se muestran las ${sel.layer.nodes.length - 1} variables que más aportaron (de ${sel.layer.total}) y la secuencia semanal.`
                  : `Se muestran ${sel.layer.nodes.length} de ${sel.layer.total} neuronas: las que más aportaron a esta predicción.`}
              </p>
              {sel.incoming.length > 0 && (
                <p><span className="text-muted">Recibe sobre todo de:</span>{" "}
                  {sel.incoming.slice(0, 3).map((e) => (
                    <span key={key(e.source_layer, e.source)} className={cx("mr-2", e.sign > 0 ? "text-teal" : "text-danger")}>
                      {labelOf(e.source_layer, e.source)} ({e.sign > 0 ? "sube" : "baja"})
                    </span>
                  ))}
                </p>
              )}
              {sel.outgoing.length > 0 && (
                <p><span className="text-muted">Envía sobre todo a:</span>{" "}
                  {sel.outgoing.slice(0, 3).map((e) => (
                    <span key={key(e.target_layer, e.target)} className={cx("mr-2", e.sign > 0 ? "text-teal" : "text-danger")}>
                      {labelOf(e.target_layer, e.target)} ({e.sign > 0 ? "sube" : "baja"})
                    </span>
                  ))}
                </p>
              )}
            </div>
          ) : (
            <p className="text-muted">
              Haz clic en una neurona para ver su activación real y de dónde recibe y a dónde envía la señal.
              El brillo es cuánto se activó; el grosor de cada conexión, cuánto aportó (verde sube, rosado baja).
            </p>
          )}
        </div>
        <div className="rounded-xl border border-line bg-bg/40 p-3">
          <p className="font-semibold text-text">Qué explica esta probabilidad</p>
          {trace.factors.length > 0 ? (
            <ul className="mt-1.5 list-inside list-disc space-y-0.5">
              {trace.factors.map((f) => <li key={f.feature}>{f.label} <span className="text-muted">(+{Math.round(f.impact * 100)} pts)</span></li>)}
            </ul>
          ) : <p className="mt-1.5 text-muted">Sin factores destacados: la probabilidad está lejos del umbral.</p>}
          <p className="mt-2 text-muted">
            Umbral de alerta: {Math.round(trace.threshold * 100)} %. Es un apoyo para el docente, no un diagnóstico (§9.8);
            el estudiante no ve este cálculo (D22).
          </p>
        </div>
      </div>
    </div>
  );
}
