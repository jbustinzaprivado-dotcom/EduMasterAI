import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Plus, Send, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import { KIND_LABEL, type Assessment, type Attempt, type Offering } from "./api";

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "No se pudo completar la acción.");

function studentStatus(a: Assessment): { label: string; tone: "teal" | "cyan" | "warning" | "danger" | "muted" } {
  const mine = a.mine;
  if (mine?.best_score != null) return { label: `Calificada: ${mine.best_score}/${a.max_score}`, tone: "teal" };
  if (mine && mine.attempts > 0) return { label: "Entregada · por calificar", tone: "cyan" };
  if (new Date(a.due_at) < new Date()) return { label: "Vencida sin entrega", tone: "danger" };
  return { label: "Pendiente", tone: "warning" };
}

function GradePanel({ assessment, onClose }: { assessment: Assessment; onClose: () => void }) {
  const qc = useQueryClient();
  const attempts = useQuery({
    queryKey: ["attempts", assessment.id],
    queryFn: () => api<Attempt[]>(`/assessments/${assessment.id}/attempts`),
  });
  const [scores, setScores] = useState<Record<string, string>>({});
  const grade = useMutation({
    mutationFn: (t: Attempt) =>
      api<Attempt>(`/attempts/${t.id}`, { method: "PATCH", body: JSON.stringify({ score: Number(scores[t.id]), feedback: "Calificado en EduMaster." }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attempts", assessment.id] });
      qc.invalidateQueries({ queryKey: ["assessments"] });
      qc.invalidateQueries({ queryKey: ["roster"] });
    },
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Calificar">
      <div className="panel panel-glow flex max-h-[90vh] w-full max-w-2xl flex-col gap-3 overflow-y-auto p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold">{assessment.title}</h2>
            <p className="text-xs text-muted">Nota oficial sobre {assessment.max_score}. Cada cambio queda en la bitácora (§11.1).</p>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="text-muted hover:text-text"><X className="size-5" /></button>
        </div>
        {attempts.isPending && <Skeleton className="h-40" />}
        {attempts.isError && <ErrorState error={attempts.error} />}
        {attempts.data?.length === 0 && <p className="text-sm text-muted">Aún no hay entregas.</p>}
        <ul className="divide-y divide-line">
          {attempts.data?.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{t.student_name} <span className="text-xs text-muted">· intento {t.attempt_no}</span></p>
                <p className="text-xs text-muted">{formatDateTime(t.submitted_at)} {t.late && <Badge tone="warning">fuera de plazo</Badge>}</p>
                <p className="mt-1 line-clamp-2 text-xs text-text/80">{t.answer}</p>
              </div>
              <input type="number" min={0} max={assessment.max_score} step={0.5} className="field w-20" aria-label={`Nota de ${t.student_name}`}
                placeholder={t.score?.toString() ?? "—"} value={scores[t.id] ?? ""} onChange={(e) => setScores((s) => ({ ...s, [t.id]: e.target.value }))} />
              <Button variant="ghost" className="px-2.5 py-1.5 text-xs" disabled={!scores[t.id]}
                loading={grade.isPending && grade.variables?.id === t.id} onClick={() => grade.mutate(t)}>
                {t.score != null ? "Corregir" : "Calificar"}
              </Button>
            </li>
          ))}
        </ul>
        {grade.isError && <p role="alert" className="text-sm text-danger">{errText(grade.error)}</p>}
      </div>
    </div>
  );
}

function SubmitDialog({ assessment, onClose }: { assessment: Assessment; onClose: () => void }) {
  const qc = useQueryClient();
  const [answer, setAnswer] = useState("");
  const submit = useMutation({
    mutationFn: () => api<Assessment>(`/assessments/${assessment.id}/submissions`, { method: "POST", body: JSON.stringify({ answer }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Entregar">
      <form className="panel panel-glow flex w-full max-w-lg flex-col gap-3 p-5" onSubmit={(e: FormEvent) => { e.preventDefault(); submit.mutate(); }}>
        <h2 className="font-semibold">{assessment.title}</h2>
        {assessment.instructions && <p className="text-sm text-muted">{assessment.instructions}</p>}
        <label className="label" htmlFor="answer">Tu respuesta</label>
        <textarea id="answer" className="field min-h-32" value={answer} onChange={(e) => setAnswer(e.target.value)} required />
        <p className="text-xs text-muted">Intentos: {assessment.mine?.attempts ?? 0} de {assessment.max_attempts}. Vence: {formatDateTime(assessment.due_at)}.</p>
        {submit.isError && <p role="alert" className="text-sm text-danger">{errText(submit.error)}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" icon={Send} loading={submit.isPending} disabled={!answer.trim()}>Entregar</Button>
        </div>
      </form>
    </div>
  );
}

function NewAssessmentDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const [form, setForm] = useState({ offering: "", title: "", kind: "practica", weight: "20", due: "", attempts: "1", instructions: "" });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = useMutation({
    mutationFn: () => api<Assessment>(`/offerings/${form.offering}/assessments`, {
      method: "POST",
      body: JSON.stringify({
        title: form.title, kind: form.kind, weight: Number(form.weight) / 100, max_attempts: Number(form.attempts),
        due_at: new Date(`${form.due}T23:59:00`).toISOString(), instructions: form.instructions, max_score: 20,
      }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assessments"] });
      onClose();
    },
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Nueva evaluación">
      <form className="panel panel-glow grid w-full max-w-lg gap-3 p-5 sm:grid-cols-2" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <h2 className="font-semibold sm:col-span-2">Nueva evaluación</h2>
        <div className="sm:col-span-2"><label className="label" htmlFor="a-off">Oferta</label>
          <select id="a-off" className="field" value={form.offering} onChange={set("offering")} required>
            <option value="">Selecciona…</option>
            {offerings.data?.filter((o) => o.can_manage).map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.cohort}</option>)}
          </select></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="a-title">Título</label>
          <input id="a-title" className="field" value={form.title} onChange={set("title")} required minLength={3} /></div>
        <div><label className="label" htmlFor="a-kind">Tipo</label>
          <select id="a-kind" className="field" value={form.kind} onChange={set("kind")}>
            {["opcion_multiple", "verdadero_falso", "respuesta_corta", "archivo", "practica"].map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select></div>
        <div><label className="label" htmlFor="a-w">Peso (%)</label>
          <input id="a-w" type="number" min={1} max={100} className="field" value={form.weight} onChange={set("weight")} required /></div>
        <div><label className="label" htmlFor="a-due">Vence</label>
          <input id="a-due" type="date" className="field" value={form.due} onChange={set("due")} required /></div>
        <div><label className="label" htmlFor="a-att">Intentos</label>
          <input id="a-att" type="number" min={1} max={10} className="field" value={form.attempts} onChange={set("attempts")} /></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="a-ins">Instrucciones</label>
          <textarea id="a-ins" className="field min-h-16" value={form.instructions} onChange={set("instructions")} /></div>
        {save.isError && <p role="alert" className="text-sm text-danger sm:col-span-2">{errText(save.error)}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={save.isPending}>Publicar</Button>
        </div>
      </form>
    </div>
  );
}

export function AssessmentsPage() {
  const { can } = useAuth();
  const assessments = useQuery({ queryKey: ["assessments"], queryFn: () => api<Assessment[]>("/assessments") });
  const [grading, setGrading] = useState<Assessment | null>(null);
  const [submitting, setSubmitting] = useState<Assessment | null>(null);
  const [creating, setCreating] = useState(false);
  const student = can("learning") && !can("course.read.all");

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Evaluaciones"
        description={student ? "Tus entregas y notas oficiales." : "Entregas por evaluación. La nota oficial la registra el docente; la IA nunca califica (§4.6)."}
        actions={can("assessment.manage") && <Button icon={Plus} onClick={() => setCreating(true)}>Nueva evaluación</Button>} />
      <Panel>
        {assessments.isPending && <Skeleton className="h-64" />}
        {assessments.isError && <ErrorState error={assessments.error} onRetry={() => assessments.refetch()} />}
        {assessments.data?.length === 0 && <EmptyState icon={ClipboardCheck} title="Sin evaluaciones" description="No hay evaluaciones en tus cursos." />}
        <ul className="divide-y divide-line">
          {assessments.data?.map((a) => {
            const status = studentStatus(a);
            const open = new Date(a.due_at) > new Date() || (a.mine?.attempts ?? 0) === 0;
            return (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-3">
                <ClipboardCheck className="size-5 shrink-0 text-violet" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{a.title}</p>
                  <p className="text-xs text-muted">{a.course_title} · {a.cohort} · {KIND_LABEL[a.kind]} · peso {Math.round(a.weight * 100)} % · vence {formatDateTime(a.due_at)}</p>
                </div>
                {a.mine && <Badge tone={status.tone}>{status.label}</Badge>}
                {a.mine && a.mine.attempts < a.max_attempts && open && (
                  <Button variant="ghost" icon={Send} className="px-2.5 py-1.5 text-xs" onClick={() => setSubmitting(a)}>Entregar</Button>
                )}
                {a.can_manage && (
                  <>
                    <span className={cx("text-xs", a.graded === a.submissions ? "text-muted" : "text-warning")}>
                      {a.submissions} entregas · {a.graded} calificadas
                    </span>
                    <Button variant="ghost" className="px-2.5 py-1.5 text-xs" onClick={() => setGrading(a)}>Calificar</Button>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      </Panel>
      {grading && <GradePanel assessment={grading} onClose={() => setGrading(null)} />}
      {submitting && <SubmitDialog assessment={submitting} onClose={() => setSubmitting(null)} />}
      {creating && <NewAssessmentDialog onClose={() => setCreating(false)} />}
    </div>
  );
}
