import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, Check, RotateCcw, Sparkles, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { Link } from "react-router";
import { Badge, Button, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";

export interface Recommendation {
  id: string;
  offering_id: string;
  course_title: string;
  student_name: string | null;
  kind: "siguiente_actividad" | "entrega_proxima" | "reforzar" | "retomar";
  target_type: "activity" | "assessment";
  target_id: string;
  title: string;
  reason: string;
  expected_impact: string;
  priority: number;
  source: string;
  status: "nueva" | "aceptada" | "descartada" | "completada" | "expirada";
  useful: boolean | null;
  feedback_reason: string | null;
  created_at: string;
  resolved_at: string | null;
}

export const KIND_META = {
  siguiente_actividad: { label: "Siguiente actividad", icon: ArrowRight, tone: "cyan" },
  entrega_proxima: { label: "Entrega próxima", icon: CalendarClock, tone: "warning" },
  reforzar: { label: "Reforzar", icon: RotateCcw, tone: "violet" },
  retomar: { label: "Retomar", icon: Sparkles, tone: "teal" },
} as const;

export const STATUS_TONE = {
  nueva: "cyan", aceptada: "violet", completada: "teal", descartada: "muted", expirada: "muted",
} as const;

export function RecommendationCard({ r, compact = false }: { r: Recommendation; compact?: boolean }) {
  const qc = useQueryClient();
  const send = useMutation({
    mutationFn: (body: { action: string; reason?: string }) =>
      api<Recommendation>(`/recommendations/${r.id}/feedback`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });
  const meta = KIND_META[r.kind];
  const open = r.status === "nueva" || r.status === "aceptada";
  const href = r.target_type === "assessment" ? "/evaluaciones" : `/cursos/${r.offering_id}`;

  return (
    <article className={cx("panel flex flex-col gap-2 p-4", r.status === "nueva" && "panel-glow")}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={meta.tone}><meta.icon className="size-3" /> {meta.label}</Badge>
        <span className="text-[11px] text-muted">{r.course_title}</span>
        <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
      </div>
      <h3 className="font-semibold">{r.title}</h3>
      <p className="text-sm text-muted"><span className="text-text/80">Por qué: </span>{r.reason}</p>
      {!compact && <p className="text-xs text-muted">Impacto esperado: <span className="text-text">{r.expected_impact}</span></p>}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <Link to={href} className="inline-flex items-center gap-1 rounded-[10px] bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1a8cf0]"
          onClick={() => r.status === "nueva" && send.mutate({ action: "aceptar" })}>
          Ir ahora <ArrowRight className="size-3.5" />
        </Link>
        {r.status === "nueva" && (
          <Button variant="ghost" icon={Check} className="px-2.5 py-1.5 text-xs" onClick={() => send.mutate({ action: "aceptar" })}>Aceptar</Button>
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
