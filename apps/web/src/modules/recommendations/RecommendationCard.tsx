import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlarmClock, ArrowRight, Award, CalendarClock, Gauge, Megaphone, Route, RotateCcw, Sparkles, ThumbsDown, ThumbsUp,
  TrendingUp, X,
} from "lucide-react";
import { Link } from "react-router";
import { Badge, Button, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

export interface Recommendation {
  id: string;
  offering_id: string;
  course_title: string;
  student_name: string | null;
  kind: keyof typeof KIND_META;
  target_type: "activity" | "assessment" | "skill" | "path" | "post" | "offering";
  target_id: string;
  title: string;
  reason: string;
  expected_impact: string;
  priority: number;
  priority_reason: string;
  source: string;
  status: "nueva" | "aceptada" | "descartada" | "completada" | "expirada";
  useful: boolean | null;
  feedback_reason: string | null;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
}

/** Tipos de sugerencia (D27, D55): nombre, ícono, color y el texto del botón de acción. */
export const KIND_META = {
  siguiente_actividad: { label: "Siguiente actividad", icon: ArrowRight, tone: "cyan", action: "Ir a la actividad" },
  entrega_proxima: { label: "Entrega próxima", icon: CalendarClock, tone: "warning", action: "Entregar" },
  vencida: { label: "Entrega vencida", icon: AlarmClock, tone: "danger", action: "Entregar ahora" },
  mejorar_nota: { label: "Mejorar nota", icon: TrendingUp, tone: "violet", action: "Intentar de nuevo" },
  reforzar: { label: "Reforzar", icon: RotateCcw, tone: "violet", action: "Repasar" },
  retomar: { label: "Retomar", icon: Sparkles, tone: "teal", action: "Retomar" },
  competencia: { label: "Competencia", icon: Gauge, tone: "cyan", action: "Ver mi nivel" },
  certificado: { label: "Certificado", icon: Award, tone: "teal", action: "Ver qué me falta" },
  ruta: { label: "Ruta", icon: Route, tone: "violet", action: "Empezar la etapa" },
  anuncio: { label: "Anuncio", icon: Megaphone, tone: "warning", action: "Leer el anuncio" },
} as const;

export const STATUS_TONE = {
  nueva: "cyan", aceptada: "violet", completada: "teal", descartada: "muted", expirada: "muted",
} as const;

/** A dónde lleva el botón de acción según lo que se sugiere. */
export function targetHref(r: Recommendation): string {
  switch (r.target_type) {
    case "activity": return `/cursos/${r.offering_id}/actividad/${r.target_id}`;
    case "assessment": return "/evaluaciones";
    case "skill": return "/habilidades";
    case "path": return "/rutas";
    case "post": return `/comunidad?oferta=${r.offering_id}&post=${r.target_id}`;
    default: return `/cursos/${r.offering_id}`;
  }
}

export function RecommendationCard({ r, compact = false }: { r: Recommendation; compact?: boolean }) {
  const qc = useQueryClient();
  const send = useMutation({
    mutationFn: (body: { action: string; reason?: string }) =>
      api<Recommendation>(`/recommendations/${r.id}/feedback`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });
  const meta = KIND_META[r.kind] ?? KIND_META.siguiente_actividad;
  const open = r.status === "nueva" || r.status === "aceptada";

  return (
    <article className={cx("panel flex flex-col gap-2 p-4", r.status === "nueva" && "panel-glow")}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={meta.tone}><meta.icon className="size-3" /> {meta.label}</Badge>
        <span className="text-[11px] text-muted">{r.course_title}</span>
        <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
        {open && r.priority_reason && <span className="ml-auto text-[11px] text-muted" title="Por qué va en este lugar">Prioridad: {r.priority_reason}</span>}
      </div>
      <h3 className="font-semibold">{r.title}</h3>
      <p className="text-sm text-muted"><span className="text-text/80">Por qué: </span>{r.reason}</p>
      {!compact && <p className="text-xs text-muted">Impacto esperado: <span className="text-text">{r.expected_impact}</span></p>}
      {!open && r.resolution_note && (
        <p className="text-xs text-muted">Se cerró {r.resolved_at ? formatDateTime(r.resolved_at) : ""}: <span className="text-text">{r.resolution_note}</span></p>
      )}
      {r.status === "descartada" && r.feedback_reason && <p className="text-xs text-muted">Motivo del descarte: {r.feedback_reason}</p>}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {open && (
          // Un solo botón de acción: ir a hacerlo cuenta como aceptar la sugerencia (D55).
          <Link to={targetHref(r)} className="inline-flex items-center gap-1 rounded-[10px] bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1a8cf0]"
            onClick={() => r.status === "nueva" && send.mutate({ action: "aceptar" })}>
            {meta.action} <ArrowRight className="size-3.5" />
          </Link>
        )}
        {open && (
          <Button variant="ghost" icon={X} className="px-2.5 py-1.5 text-xs" onClick={() => {
            const reason = window.prompt("¿Por qué no te sirve? (opcional)") ?? undefined;
            send.mutate({ action: "descartar", reason });
          }}>Descartar</Button>
        )}
        {!compact && (
          <span className="ml-auto flex items-center gap-1 text-xs text-muted">
            ¿Útil?
            <button aria-label="Útil" aria-pressed={r.useful === true} onClick={() => send.mutate({ action: "util" })}
              className={cx("rounded-md p-1 hover:text-teal", r.useful === true && "text-teal")}><ThumbsUp className="size-4" /></button>
            <button aria-label="No útil" aria-pressed={r.useful === false} onClick={() => send.mutate({ action: "no_util" })}
              className={cx("rounded-md p-1 hover:text-danger", r.useful === false && "text-danger")}><ThumbsDown className="size-4" /></button>
          </span>
        )}
      </div>
      {send.isError && <p role="alert" className="text-xs text-danger">{send.error instanceof ApiError ? send.error.message : "Error"}</p>}
    </article>
  );
}
