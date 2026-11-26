import { useQuery } from "@tanstack/react-query";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, ErrorState, Skeleton, cx } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { Architecture } from "./NeuralNetwork";

/**
 * Recorrido real de una predicción (D51) de un estudiante o del grupo de una oferta (D52).
 * La animación es la propagación hacia delante con valores reales: los pulsos viajan solo por las conexiones que
 * existen en la red, capa por capa; su tamaño es cuánto aportaron y su color si suben (verde) o bajan (rosado) la
 * activación del destino. Cada neurona se enciende al llegarle la señal, con brillo según su activación real.
 */

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
  scope: "student" | "group";
  enrollment_id: string | null;
  student_name: string;
  course: string;
  model_version: string;
  computed_at: string;
  count: number;
  probability: number;
  threshold: number;
  risk_level: "alto" | "medio" | "bajo";
  levels: { alto: number; medio: number; bajo: number };
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
const H = 440;
const PAD_L = 185; // cabe "Evaluaciones sin entregar 0.50"
const PAD_R = 185; // cabe "C · Riesgo de abandono · 80 %"
const TOP = 30; // borde superior del dibujo
const BOTTOM = H - 34; // borde inferior (debajo van los nombres de las capas)
const STEP_Y = 30; // separación entre neuronas de una rama
const HOP_S = 0.9; // segundos que tarda la señal en pasar de una columna a la siguiente (1×)

/**
 * Columnas de la topología real: la rama tabular y el bloque temporal son PARALELOS (§9.1), así que comparten la
 * columna 1 (tabular arriba, temporal abajo). Ninguna conexión salta una columna ni cruza neuronas ajenas, y la
 * señal llega a las dos ramas a la vez.
 */
const COLUMN: Record<TraceLayer["id"], number> = { input: 0, projection: 1, temporal: 1, fusion: 2, heads: 3 };
const LAST = 3;
const MODES = [["all", "Todas las variables"], ["turns", "Por turnos"]] as const;

type Point = [number, number];
type Selection = { kind: "node"; key: string } | { kind: "layer"; id: string } | null;
const key = (layer: string, index: number) => `${layer}:${index}`;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function fmt(value: number | null) {
  return value === null ? "sin entrenar" : value.toFixed(3);
}

/** Punto de la curva de una conexión (Bézier cúbica horizontal) en t ∈ [0, 1]. */
function onCurve([x1, y1]: Point, [x2, y2]: Point, t: number): Point {
  const mx = (x1 + x2) / 2;
  const u = 1 - t;
  const a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
  return [a * x1 + b * mx + c * mx + d * x2, a * y1 + b * y1 + c * y2 + d * y2];
}

export function useTrace(offeringId: string | null, enrollment: string | null) {
  const group = enrollment === "todos";
  return useQuery({
    queryKey: ["ml", "trace", group ? offeringId : enrollment],
    queryFn: () => api<Trace>(group ? `/ml/offerings/${offeringId}/trace` : `/ml/enrollments/${enrollment}/trace`),
    enabled: !!enrollment && (!group || !!offeringId),
    staleTime: 60_000,
  });
}

export function TraceView({ arch, offeringId, enrollment }: { arch: Architecture; offeringId: string | null; enrollment: string }) {
  const query = useTrace(offeringId, enrollment);
  if (query.isPending) return <Skeleton className="h-80" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <TraceDiagram arch={arch} trace={query.data} />;
}

export function TraceDiagram({ arch, trace }: { arch: Architecture; trace: Trace }) {
  const reduced = useMemo(prefersReducedMotion, []);
  const last = LAST;
  const inputs = trace.layers[0]!.nodes;
  const [selected, setSelected] = useState<Selection>(null);
  const [playing, setPlaying] = useState(!reduced);
  const [speed, setSpeed] = useState(1);
  // Modo (D53): todas las variables a la vez, una tras otra por turnos, o una variable elegida.
  const [mode, setMode] = useState<"all" | "turns" | "one">("all");
  const [focusVar, setFocusVar] = useState<number | null>(null);
  // step = última columna encendida; t = avance hacia la siguiente; rest = pausa entre turnos; turn = variable actual.
  const anim = useRef({ step: reduced ? last : 0, t: 0, rest: 0, turn: 0 });
  const [, setFrame] = useState(0);
  const redraw = () => setFrame((f) => (f + 1) % 1_000_000);

  const replay = () => { anim.current = { step: reduced ? last : 0, t: 0, rest: 0, turn: 0 }; setPlaying(!reduced); redraw(); };
  // Otra traza, otro modo u otra variable: el recorrido empieza de nuevo desde la entrada.
  useEffect(() => { setSelected(null); }, [trace]);
  useEffect(replay, [trace, reduced, mode, focusVar]); // eslint-disable-line react-hooks/exhaustive-deps

  const focusing = mode !== "all";
  const hop = HOP_S * (focusing ? 1.5 : 1);
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let prev = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(now - prev, 250) / 1000;
      prev = now;
      const a = anim.current;
      if (a.rest > 0) {
        a.rest -= dt * speed;
        if (a.rest <= 0) { a.rest = 0; a.turn += 1; a.step = 0; a.t = 0; } // siguiente variable
      } else {
        a.t += (dt * speed) / hop;
        if (a.t >= 1) { a.step += 1; a.t = 0; }
        if (a.step >= last) {
          a.step = last;
          if (mode === "turns" && a.turn < inputs.length - 1) a.rest = 1.1; // pausa y pasa a la siguiente
          else { redraw(); setPlaying(false); return; } // la señal llegó a la salida
        }
      }
      redraw();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, last, hop, mode, inputs.length]);

  const { step, t, turn } = anim.current;
  const done = step >= last;
  const layerIndex = useMemo(() => new Map(trace.layers.map((l) => [l.id as string, COLUMN[l.id]])), [trace]);
  const pos = useMemo(() => {
    const map = new Map<string, Point>();
    const tabular = trace.layers.find((l) => l.id === "projection")?.nodes.length ?? 0;
    const branchTop = { projection: TOP + 22, temporal: TOP + 22 + (tabular - 1) * STEP_Y + 46 };
    trace.layers.forEach((layer) => {
      const x = PAD_L + (COLUMN[layer.id] * (W - PAD_L - PAD_R)) / LAST;
      const n = layer.nodes.length;
      layer.nodes.forEach((node, j) => {
        let y: number;
        if (layer.id === "projection" || layer.id === "temporal") {
          y = branchTop[layer.id] + j * STEP_Y; // cada rama en su mitad de la columna, con su nombre encima
        } else {
          const gap = layer.id === "input" ? (BOTTOM - TOP - 10) / Math.max(n - 1, 1) : Math.min(54, (BOTTOM - TOP) / Math.max(n - 1, 1));
          y = (TOP + BOTTOM) / 2 - (gap * (n - 1)) / 2 + j * gap;
        }
        map.set(key(layer.id, node.index), [x, y]);
      });
    });
    return map;
  }, [trace]);

  // Camino de cada variable: las neuronas y conexiones que alcanza su señal, de la entrada a la salida.
  const reach = useMemo(() => {
    const out = new Map<string, number[]>();
    trace.edges.forEach((e, k) => {
      const s = key(e.source_layer, e.source);
      out.set(s, [...(out.get(s) ?? []), k]);
    });
    return new Map(inputs.map((n) => {
      const nodes = new Set<string>([key("input", n.index)]);
      const edges = new Set<number>();
      const queue = [key("input", n.index)];
      while (queue.length) {
        for (const k of out.get(queue.shift()!) ?? []) {
          const e = trace.edges[k]!;
          const target = key(e.target_layer, e.target);
          edges.add(k);
          if (!nodes.has(target)) { nodes.add(target); queue.push(target); }
        }
      }
      return [n.index, { nodes, edges }] as const;
    }));
  }, [trace, inputs]);
  const focusIndex = mode === "one" ? focusVar : mode === "turns" ? inputs[Math.min(turn, inputs.length - 1)]?.index ?? null : null;
  const focus = focusIndex !== null ? reach.get(focusIndex) ?? null : null;
  const focusNode = focusIndex !== null ? inputs.find((n) => n.index === focusIndex) ?? null : null;

  // Señal en tránsito hacia la columna step + 1. Con una variable en foco, sus neuronas destino se encienden por
  // turnos (de arriba abajo); con todas, salen primero los pulsos que más aportan.
  const travelling = trace.edges.map((e, k) => ({ e, k }))
    .filter(({ e, k }) => !done && layerIndex.get(e.target_layer) === step + 1 && (!focus || focus.edges.has(k)));
  const order = [...new Set(travelling.map(({ e }) => key(e.target_layer, e.target)))]
    .sort((a, b) => pos.get(a)![1] - pos.get(b)![1]);
  const progress = (e: TraceEdge) => {
    if (focus) {
      const rank = order.indexOf(key(e.target_layer, e.target));
      const delay = order.length > 1 ? (0.55 * rank) / (order.length - 1) : 0;
      return Math.min(Math.max((t - delay) / 0.45, 0), 1);
    }
    const delay = 0.35 * (1 - e.strength);
    return Math.min(Math.max((t - delay) / (1 - delay), 0), 1);
  };
  const arrived = new Set(order.filter((k) => travelling.filter(({ e }) => key(e.target_layer, e.target) === k).every(({ e }) => progress(e) >= 1)));
  const isLit = (k: string, col: number) => (col <= step || (col === step + 1 && arrived.has(k))) && (!focus || focus.nodes.has(k));

  const labelOf = (layerId: string, index: number) =>
    trace.layers.find((l) => l.id === layerId)?.nodes.find((n) => n.index === index)?.label ?? "";
  const selNode = selected?.kind === "node" ? (() => {
    const [layerId, idx] = selected.key.split(":");
    const layer = trace.layers.find((l) => l.id === layerId)!;
    const node = layer.nodes.find((n) => n.index === Number(idx))!;
    const incoming = trace.edges.filter((e) => e.target_layer === layerId && e.target === node.index).sort((a, b) => b.strength - a.strength);
    const outgoing = trace.edges.filter((e) => e.source_layer === layerId && e.source === node.index).sort((a, b) => b.strength - a.strength);
    return { layer, node, incoming, outgoing };
  })() : null;
  const selLayer = selected?.kind === "layer" ? arch.layers.find((l) => l.id === selected.id) : null;
  const selLayerTrace = selected?.kind === "layer" ? trace.layers.find((l) => l.id === selected.id) : null;
  const linked = new Set(selNode ? [...selNode.incoming.map((e) => key(e.source_layer, e.source)),
    ...selNode.outgoing.map((e) => key(e.target_layer, e.target))] : []);
  const group = trace.scope === "group";
  const selKey = selected?.kind === "node" ? selected.key : null;
  const pct = Math.round(trace.probability * 100);
  const pathSize = focus ? [...focus.nodes].filter((k) => !k.startsWith("input:") && !k.startsWith("heads:")).length : 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge tone="cyan">Datos reales · modelo v{trace.model_version}</Badge>
        <span className="font-semibold text-text">{trace.student_name}</span>
        <span className="text-muted">{trace.course}</span>
        {group ? (
          <>
            <Badge tone="danger">Alto: {trace.levels.alto}</Badge>
            <Badge tone="warning">Medio: {trace.levels.medio}</Badge>
            <Badge tone="teal">Bajo: {trace.levels.bajo}</Badge>
          </>
        ) : (
          <Badge tone={RISK_TONE[trace.risk_level]}>Riesgo {trace.risk_level} · {pct} %</Badge>
        )}
        <div className="ml-auto flex items-center gap-2">
          {reduced ? (
            <span className="text-[11px] text-muted">Animación desactivada (movimiento reducido)</span>
          ) : (
            <>
              <Button variant="ghost" icon={playing ? Pause : Play} className="px-2.5 py-1.5 text-xs"
                onClick={() => (done && anim.current.rest === 0 ? replay() : setPlaying((v) => !v))}>
                {playing ? "Pausar" : done ? "Repetir" : "Reanudar"}
              </Button>
              <Button variant="ghost" icon={RotateCcw} onClick={replay} className="px-2.5 py-1.5 text-xs" aria-label="Recorrer de nuevo" />
              <label className="sr-only" htmlFor="trace-speed">Velocidad</label>
              <select id="trace-speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="field w-auto px-2 py-1 text-xs">
                <option value={0.5}>0.5×</option>
                <option value={1}>1×</option>
                <option value={2}>2×</option>
              </select>
            </>
          )}
        </div>
      </div>

      {/* Modo del recorrido (D53) */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <div role="group" aria-label="Modo del recorrido" className="flex overflow-hidden rounded-[10px] border border-line">
          {(reduced ? MODES.slice(0, 1) : MODES).map(([m, label]) => (
            <button key={m} type="button" aria-pressed={mode === m}
              className={cx("px-2.5 py-1.5", mode === m ? "bg-primary/20 text-cyan" : "text-muted hover:text-text")}
              onClick={() => { setMode(m); setFocusVar(null); }}>{label}</button>
          ))}
        </div>
        <label className="sr-only" htmlFor="trace-variable">Variable específica</label>
        <select id="trace-variable" className="field w-auto px-2 py-1 text-xs" value={mode === "one" && focusVar !== null ? focusVar : ""}
          onChange={(e) => { if (e.target.value === "") { setMode("all"); setFocusVar(null); } else { setMode("one"); setFocusVar(Number(e.target.value)); } }}>
          <option value="">Variable específica…</option>
          {inputs.map((n) => <option key={n.index} value={n.index}>{n.label}</option>)}
        </select>
        {focusNode && (
          <span data-testid="trace-focus" className="text-muted">
            {mode === "turns" && <>Variable {Math.min(turn, inputs.length - 1) + 1} de {inputs.length} · </>}
            <span className="font-semibold text-text">{focusNode.label}</span> ({focusNode.value?.toFixed(2)}): su señal pasa por{" "}
            {pathSize} neuronas hasta la salida{focusNode.intensity < 0.05 ? "; con valor casi 0, aporta muy poco" : ""}.
          </span>
        )}
      </div>

      {/* En pantallas angostas el diagrama conserva un ancho legible y se desplaza dentro del panel */}
      <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" data-testid="trace-svg"
        aria-label={group
          ? `Recorrido del grupo de ${trace.count} estudiantes: ${pct} % de riesgo promedio`
          : `Recorrido de la predicción de ${trace.student_name}: ${pct} % de riesgo`}
        className="w-full min-w-[680px] rounded-xl bg-[radial-gradient(ellipse_at_center,rgb(0_191_166/0.08),transparent_70%)]">
        {/* Conexiones reales: las ya recorridas se ven con su fuerza; las que recorre la señal ahora, tenues */}
        {trace.edges.map((e, k) => {
          const target = layerIndex.get(e.target_layer)!;
          if (target > step + 1) return null;
          const from = pos.get(key(e.source_layer, e.source))!;
          const to = pos.get(key(e.target_layer, e.target))!;
          const mx = (from[0] + to[0]) / 2;
          const inFocus = !focus || focus.edges.has(k);
          const onPath = inFocus && (!selNode || selKey === key(e.source_layer, e.source) || selKey === key(e.target_layer, e.target));
          const moving = target === step + 1;
          return (
            <path key={k} d={`M${from[0]} ${from[1]}C${mx} ${from[1]} ${mx} ${to[1]} ${to[0]} ${to[1]}`} fill="none"
              stroke={e.sign > 0 ? UP : DOWN} strokeWidth={0.6 + 2.6 * e.strength}
              strokeOpacity={!inFocus ? 0.04 : moving ? 0.1 : onPath ? 0.2 + 0.65 * e.strength : 0.06} />
          );
        })}
        {/* Pulsos de la señal viajando hacia la siguiente columna */}
        <g pointerEvents="none">
          {travelling.map(({ e, k }) => {
            const te = progress(e);
            if (te <= 0 || te >= 1) return null;
            const [x, y] = onCurve(pos.get(key(e.source_layer, e.source))!, pos.get(key(e.target_layer, e.target))!, te);
            return <circle key={k} cx={x} cy={y} r={1.8 + 2.6 * e.strength} fill={e.sign > 0 ? UP : DOWN} fillOpacity={0.9} />;
          })}
        </g>
        {trace.layers.map((layer) => {
          const col = COLUMN[layer.id];
          const branch = layer.id === "projection" || layer.id === "temporal";
          const [lx, firstY] = pos.get(key(layer.id, layer.nodes[0]!.index))!;
          const layerSel = selected?.kind === "layer" && selected.id === layer.id;
          return (
            <g key={layer.id}>
              {layer.nodes.map((node) => {
                const k = key(layer.id, node.index);
                const [x, y] = pos.get(k)!;
                const isSel = selKey === k;
                const lit = isLit(k, col);
                const outOfFocus = !!focus && !focus.nodes.has(k);
                const dim = outOfFocus || (selNode && !isSel && !linked.has(k)) || !lit;
                const planned = node.value === null;
                const glow = lit && !planned;
                return (
                  <g key={k} className="cursor-pointer" role="button" tabIndex={0} aria-pressed={isSel}
                    aria-label={`${layer.name}, ${node.label}: ${fmt(node.value)}`}
                    onClick={() => setSelected(isSel ? null : { kind: "node", key: k })}
                    onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && setSelected(isSel ? null : { kind: "node", key: k })}
                    opacity={outOfFocus ? 0.15 : dim ? 0.3 : 1}>
                    <title>{`${node.label} · ${fmt(node.value)}`}</title>
                    {glow && <circle cx={x} cy={y} r={9 + 5 * node.intensity} fill={COLOR[layer.id]} fillOpacity={0.08 + 0.3 * node.intensity} />}
                    <circle cx={x} cy={y} r={isSel ? 8.5 : 7} fill={planned || !lit ? "#06152b" : COLOR[layer.id]}
                      fillOpacity={planned || !lit ? 1 : 0.15 + 0.8 * node.intensity}
                      stroke={planned ? "#4a5d7a" : COLOR[layer.id]} strokeWidth={isSel || layerSel ? 2.6 : 1.6}
                      strokeDasharray={planned ? "3 3" : undefined} />
                  </g>
                );
              })}
              <text x={lx} y={branch ? firstY - 20 : H - 8} textAnchor="middle" fontSize={11}
                fill={layerSel ? "#eaf2ff" : "#8ea3c2"} className="cursor-pointer" role="button" tabIndex={0}
                aria-label={`Capa ${layer.name}`} aria-pressed={layerSel}
                onClick={() => setSelected(layerSel ? null : { kind: "layer", id: layer.id })}
                onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && setSelected(layerSel ? null : { kind: "layer", id: layer.id })}>
                {layer.name}
              </text>
            </g>
          );
        })}
        {/* Variables de entrada con su valor real y cabezas de salida con la probabilidad */}
        {inputs.map((node) => {
          const [x, y] = pos.get(key("input", node.index))!;
          const on = !focus || focusIndex === node.index;
          return (
            <text key={`in-${node.index}`} x={x - 14} y={y + 3.5} textAnchor="end" fontSize={10.5}
              fill={on ? "#9fb4d4" : "#4a5d7a"} fontWeight={focus && on ? 600 : 400}>
              {node.label} <tspan fill={on ? "#eaf2ff" : "#4a5d7a"}>{node.value?.toFixed(2)}</tspan>
            </text>
          );
        })}
        {trace.layers.find((l) => l.id === "heads")!.nodes.map((node) => {
          const [x, y] = pos.get(key("heads", node.index))!;
          const reached = done && node.value !== null;
          return (
            <text key={`out-${node.index}`} x={x + 14} y={y + 3.5} fontSize={10.5}
              fill={node.value === null ? "#6b7f9e" : "#00bfa6"} fontWeight={node.value === null ? 400 : 600}>
              {node.label}{reached && ` · ${Math.round(node.value! * 100)} %`}
            </text>
          );
        })}
      </svg>
      </div>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-xl border border-line bg-bg/40 p-3">
          {selNode ? (
            <div className="space-y-1.5">
              <p className="text-sm font-semibold" style={{ color: COLOR[selNode.layer.id] }}>{selNode.layer.name} · {selNode.node.label}</p>
              <p><span className="text-muted">{group ? "Activación promedio del grupo:" : "Activación real:"}</span> <code className="text-cyan">{fmt(selNode.node.value)}</code></p>
              <p className="text-muted">
                {selNode.layer.id === "heads" ? "Solo la cabeza C está entrenada; las otras 3 esperan datos reales."
                  : selNode.layer.id === "input" ? `Se muestran las ${selNode.layer.nodes.length - 1} variables que más aportaron (de ${selNode.layer.total}) y la secuencia semanal.`
                  : `Se muestran ${selNode.layer.nodes.length} de ${selNode.layer.total} neuronas: las que más aportaron a esta predicción.`}
              </p>
              {selNode.incoming.length > 0 && (
                <p><span className="text-muted">Recibe sobre todo de:</span>{" "}
                  {selNode.incoming.slice(0, 3).map((e) => (
                    <span key={key(e.source_layer, e.source)} className={cx("mr-2", e.sign > 0 ? "text-teal" : "text-danger")}>
                      {labelOf(e.source_layer, e.source)} ({e.sign > 0 ? "sube" : "baja"})
                    </span>
                  ))}
                </p>
              )}
              {selNode.outgoing.length > 0 && (
                <p><span className="text-muted">Envía sobre todo a:</span>{" "}
                  {selNode.outgoing.slice(0, 3).map((e) => (
                    <span key={key(e.target_layer, e.target)} className={cx("mr-2", e.sign > 0 ? "text-teal" : "text-danger")}>
                      {labelOf(e.target_layer, e.target)} ({e.sign > 0 ? "sube" : "baja"})
                    </span>
                  ))}
                </p>
              )}
            </div>
          ) : selLayer && selLayerTrace ? (
            <div className="space-y-1">
              <p className="text-sm font-semibold" style={{ color: COLOR[selLayerTrace.id] }}>{selLayer.name}</p>
              <p><span className="text-muted">Operación:</span> {selLayer.operation}</p>
              <p><span className="text-muted">Unidades:</span> {selLayer.units} · se muestran {selLayerTrace.nodes.length}</p>
              <p><span className="text-muted">Dimensión:</span> <code className="text-cyan">{selLayer.dimension}</code></p>
            </div>
          ) : (
            <p className="text-muted">
              La señal recorre la red de la entrada a la salida con valores reales. Haz clic en una neurona para ver su
              activación y de dónde recibe y a dónde envía la señal, o en el nombre de una capa para ver su operación.
              El brillo es cuánto se activó; el grosor, cuánto aportó (verde sube, rosado baja).
            </p>
          )}
        </div>
        <div className="rounded-xl border border-line bg-bg/40 p-3">
          {group ? (
            <>
              <p className="font-semibold text-text">Qué muestra el recorrido del grupo</p>
              <p className="mt-1.5 text-muted">
                Promedio de las {trace.count} matrículas en curso: {pct} % de riesgo medio. Cada neurona muestra su
                activación promedio y cada conexión su aporte promedio. Para ver a una persona, elígela en el selector.
              </p>
            </>
          ) : (
            <>
              <p className="font-semibold text-text">Qué explica esta probabilidad</p>
              {trace.factors.length > 0 ? (
                <ul className="mt-1.5 list-inside list-disc space-y-0.5">
                  {trace.factors.map((f) => <li key={f.feature}>{f.label} <span className="text-muted">(+{Math.round(f.impact * 100)} pts)</span></li>)}
                </ul>
              ) : <p className="mt-1.5 text-muted">Sin factores destacados: la probabilidad está lejos del umbral.</p>}
            </>
          )}
          <p className="mt-2 text-muted">
            Umbral de alerta: {Math.round(trace.threshold * 100)} %. Calculado {formatDateTime(trace.computed_at)} con los
            datos actuales. Es un apoyo para el docente, no un diagnóstico (§9.8); el estudiante no ve este cálculo (D22).
          </p>
        </div>
      </div>
    </div>
  );
}
