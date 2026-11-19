import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, CheckCircle2, Circle, CircleDot, History, Lock, Plus, Route, ShieldCheck, Trash2, UserPlus, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { ProgressBar } from "../../components/charts";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import type { Course, Offering } from "../courses/api";

interface StepOut { id: string; position: number; course_id: string; course_code: string; course_title: string; min_grade: number | null }
interface PathOut {
  id: string; code: string; title: string; objective: string; competencies: string[]; target_weeks: number;
  status: "draft" | "published" | "archived"; version: number; steps: StepOut[]; assigned: number; completed: number; updated_at: string;
}
interface StepProgress {
  step_id: string; position: number; course_id: string; course_code: string; course_title: string; min_grade: number | null;
  status: "completado" | "en_curso" | "disponible" | "bloqueado" | "dispensado"; progress: number; grade: number | null;
  offering_id: string | null; available_offering_id: string | null; available_offering_label: string | null; note: string;
}
interface Assignment {
  id: string; path_id: string; path_title: string; path_objective: string; competencies: string[]; student_id: string;
  student_name: string; source: string; assigned_at: string; target_date: string | null; status: string; progress: number;
  completed_steps: number; total_steps: number; on_track: boolean | null; exceptions: { step_id: string; reason: string; granted_by: string }[];
  steps: StepProgress[] | null; next_step: StepProgress | null;
}
interface HistoryItem { occurred_at: string; action: string; actor_name: string | null; details: Record<string, unknown> | null }

const err = (e: unknown) => (e instanceof ApiError ? e.message : "No se pudo completar la acción.");
const STATUS_LABEL = { draft: "Borrador", published: "Publicada", archived: "Archivada" } as const;
const STEP_META = {
  completado: { icon: CheckCircle2, color: "text-teal", label: "Completado" },
  dispensado: { icon: ShieldCheck, color: "text-violet", label: "Dispensado" },
  en_curso: { icon: CircleDot, color: "text-cyan", label: "En curso" },
  disponible: { icon: Circle, color: "text-warning", label: "Disponible" },
  bloqueado: { icon: Lock, color: "text-muted", label: "Bloqueado" },
} as const;
const ACTION_LABEL: Record<string, string> = {
  "path.created": "Creó la ruta", "path.updated": "Modificó la ruta", "path.published": "Publicó",
  "path.archived": "Archivó", "path.assigned": "Asignó", "path.exception": "Autorizó una excepción",
};

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="panel panel-solid flex max-h-[90vh] w-full max-w-2xl flex-col gap-4 overflow-y-auto p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Cerrar" className="text-muted hover:text-text"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Línea de etapas: estado, avance y siguiente paso. */
function Timeline({ a }: { a: Assignment }) {
  return (
    <ol className="relative flex flex-col gap-3 border-l border-line pl-5">
      {a.steps?.map((s) => {
        const meta = STEP_META[s.status];
        return (
          <li key={s.step_id} className="relative">
            <meta.icon className={cx("absolute top-0.5 -left-[29px] size-[18px] rounded-full bg-bg", meta.color)} aria-hidden />
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">Etapa {s.position} · {s.course_title}</p>
              <Badge tone={s.status === "completado" ? "teal" : s.status === "dispensado" ? "violet" : s.status === "en_curso" ? "cyan" : s.status === "disponible" ? "warning" : "muted"}>{meta.label}</Badge>
              {s.min_grade !== null && <span className="text-[11px] text-muted">nota mínima {s.min_grade}</span>}
            </div>
            <p className="text-xs text-muted">{s.note}{s.grade !== null && ` · nota ${s.grade.toFixed(1)}`}</p>
            {(s.status === "en_curso" || s.status === "completado") && <ProgressBar value={s.progress} className="mt-1 max-w-xs" />}
            {s.offering_id && s.status === "en_curso" && <Link to={`/cursos/${s.offering_id}`} className="text-xs text-cyan hover:underline">Ir al curso →</Link>}
            {s.status === "disponible" && (
              <p className="text-xs text-warning">{s.available_offering_label ? `Hay una oferta abierta (${s.available_offering_label}): pide tu matrícula a coordinación.` : "Aún no hay una oferta abierta para este curso."}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function StudentView() {
  const mine = useQuery({ queryKey: ["paths", "mine"], queryFn: () => api<Assignment[]>("/my/paths") });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Mis rutas de aprendizaje" description="Secuencia de cursos con objetivo y competencias. Cada etapa se habilita al cumplir la anterior." />
      {mine.isPending && <Skeleton className="h-64" />}
      {mine.isError && <ErrorState error={mine.error} onRetry={() => mine.refetch()} />}
      {mine.data?.length === 0 && <EmptyState icon={Route} title="Sin rutas asignadas" description="Coordinación te asignará una ruta cuando corresponda." />}
      <div className="flex flex-col gap-4">
        {mine.data?.map((a) => (
          <Panel key={a.id} glow title={a.path_title} subtitle={a.path_objective}
            actions={<Badge tone={a.status === "completed" ? "teal" : "cyan"}>{a.status === "completed" ? "Completada" : `${a.completed_steps}/${a.total_steps} etapas`}</Badge>}>
            <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-muted">
              <ProgressBar value={a.progress} className="w-48" /> <span className="text-text">{Math.round(a.progress * 100)} %</span>
              {a.target_date && <span>Fecha objetivo: {formatDateTime(a.target_date)}</span>}
              {a.on_track === false && <Badge tone="warning">por detrás del calendario</Badge>}
              {a.on_track === true && <Badge tone="teal">a tiempo</Badge>}
            </div>
            <div className="mb-4 flex flex-wrap gap-1">{a.competencies.map((c) => <Badge key={c} tone="violet">{c}</Badge>)}</div>
            <Timeline a={a} />
            {a.next_step && (
              <p className="mt-4 rounded-xl border border-cyan/30 bg-cyan/5 p-3 text-sm">
                <b>Siguiente paso:</b> {a.next_step.course_title}. {a.next_step.status === "en_curso" ? "Revisa tus recomendaciones del curso en IA Tutor." : "Solicita tu matrícula."}
              </p>
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}

function PathForm({ initial, onClose }: { initial?: PathOut; onClose: () => void }) {
  const qc = useQueryClient();
  const courses = useQuery({ queryKey: ["courses"], queryFn: () => api<Course[]>("/courses") });
  const [code, setCode] = useState(initial?.code ?? "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [objective, setObjective] = useState(initial?.objective ?? "");
  const [competencies, setCompetencies] = useState((initial?.competencies ?? []).join(", "));
  const [weeks, setWeeks] = useState(String(initial?.target_weeks ?? 12));
  const [steps, setSteps] = useState<{ course_id: string; min_grade: string }[]>(
    initial?.steps.map((s) => ({ course_id: s.course_id, min_grade: s.min_grade?.toString() ?? "" })) ?? [{ course_id: "", min_grade: "" }]);
  const save = useMutation({
    mutationFn: () => {
      const body = {
        title, objective, target_weeks: Number(weeks),
        competencies: competencies.split(",").map((c) => c.trim()).filter(Boolean),
        steps: steps.filter((s) => s.course_id).map((s) => ({ course_id: s.course_id, min_grade: s.min_grade ? Number(s.min_grade) : null })),
      };
      return initial
        ? api<PathOut>(`/paths/${initial.id}`, { method: "PATCH", body: JSON.stringify(body) })
        : api<PathOut>("/paths", { method: "POST", body: JSON.stringify({ ...body, code }) });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["paths"] }); onClose(); },
  });
  const move = (i: number, d: number) => setSteps((s) => {
    const n = [...s]; const j = i + d;
    if (j < 0 || j >= n.length) return s;
    [n[i], n[j]] = [n[j]!, n[i]!];
    return n;
  });
  return (
    <Dialog title={initial ? `Editar ${initial.code}${initial.status === "published" ? " (creará la versión " + (initial.version + 1) + ")" : ""}` : "Nueva ruta"} onClose={onClose}>
      <form className="flex flex-col gap-3" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid gap-3 sm:grid-cols-[140px_1fr_110px]">
          <div><label className="label" htmlFor="p-code">Código</label>
            <input id="p-code" className="field uppercase" value={code} onChange={(e) => setCode(e.target.value)} disabled={!!initial} required /></div>
          <div><label className="label" htmlFor="p-title">Título</label>
            <input id="p-title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} /></div>
          <div><label className="label" htmlFor="p-weeks">Semanas</label>
            <input id="p-weeks" type="number" min={1} className="field" value={weeks} onChange={(e) => setWeeks(e.target.value)} /></div>
        </div>
        <div><label className="label" htmlFor="p-obj">Objetivo</label>
          <textarea id="p-obj" className="field min-h-16" value={objective} onChange={(e) => setObjective(e.target.value)} required minLength={10} /></div>
        <div><label className="label" htmlFor="p-comp">Competencias (separadas por coma)</label>
          <input id="p-comp" className="field" value={competencies} onChange={(e) => setCompetencies(e.target.value)} /></div>
        <fieldset className="flex flex-col gap-2">
          <legend className="label">Etapas en orden (cada una exige la anterior)</legend>
          {steps.map((s, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <span className="w-6 text-xs text-muted">{i + 1}.</span>
              <select className="field flex-1" aria-label={`Curso de la etapa ${i + 1}`} value={s.course_id}
                onChange={(e) => setSteps((x) => x.map((y, j) => (j === i ? { ...y, course_id: e.target.value } : y)))}>
                <option value="">Selecciona un curso…</option>
                {courses.data?.filter((c) => c.status !== "archived").map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}{c.status === "draft" ? " (borrador)" : ""}</option>)}
              </select>
              <input type="number" min={0} max={20} step={0.5} className="field w-28" placeholder="Nota mín." aria-label={`Nota mínima de la etapa ${i + 1}`}
                value={s.min_grade} onChange={(e) => setSteps((x) => x.map((y, j) => (j === i ? { ...y, min_grade: e.target.value } : y)))} />
              <Button type="button" variant="ghost" icon={ArrowUp} className="px-2 py-1.5" aria-label="Subir" onClick={() => move(i, -1)} />
              <Button type="button" variant="ghost" icon={ArrowDown} className="px-2 py-1.5" aria-label="Bajar" onClick={() => move(i, 1)} />
              {steps.length > 1 && <Button type="button" variant="ghost" icon={Trash2} className="px-2 py-1.5" aria-label="Quitar" onClick={() => setSteps((x) => x.filter((_, j) => j !== i))} />}
            </div>
          ))}
          <Button type="button" variant="ghost" icon={Plus} className="self-start" onClick={() => setSteps((x) => [...x, { course_id: "", min_grade: "" }])}>Agregar etapa</Button>
        </fieldset>
        {save.isError && <p role="alert" className="text-sm text-danger">{err(save.error)}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={save.isPending}>Guardar</Button>
        </div>
      </form>
    </Dialog>
  );
}

function AssignDialog({ path, onClose }: { path: PathOut; onClose: () => void }) {
  const qc = useQueryClient();
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const [offeringId, setOfferingId] = useState("");
  const [date, setDate] = useState("");
  const assign = useMutation({
    mutationFn: () => api<{ created: number; skipped: number }>(`/paths/${path.id}/assignments`, {
      method: "POST",
      body: JSON.stringify({ cohort_offering_id: offeringId, target_date: date ? new Date(`${date}T23:59:00`).toISOString() : null }),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paths"] }),
  });
  return (
    <Dialog title={`Asignar «${path.title}»`} onClose={onClose}>
      <p className="text-sm text-muted">Asigna la ruta a toda una cohorte (los matriculados en una oferta). Quien ya la tiene se omite.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="label" htmlFor="a-off">Cohorte</label>
          <select id="a-off" className="field" value={offeringId} onChange={(e) => setOfferingId(e.target.value)}>
            <option value="">Selecciona…</option>
            {offerings.data?.map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.cohort} ({o.enrolled})</option>)}
          </select></div>
        <div><label className="label" htmlFor="a-date">Fecha objetivo</label>
          <input id="a-date" type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} /></div>
      </div>
      {assign.isError && <p role="alert" className="text-sm text-danger">{err(assign.error)}</p>}
      {assign.isSuccess && <p className="text-sm text-teal">{assign.data.created} asignadas · {assign.data.skipped} ya la tenían. Se les notificó.</p>}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cerrar</Button>
        <Button icon={UserPlus} loading={assign.isPending} disabled={!offeringId} onClick={() => assign.mutate()}>Asignar</Button>
      </div>
    </Dialog>
  );
}

function PathDetail({ path }: { path: PathOut }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const rows = useQuery({ queryKey: ["paths", "assignments", path.id], queryFn: () => api<Assignment[]>(`/paths/${path.id}/assignments`) });
  const history = useQuery({ queryKey: ["paths", "history", path.id], queryFn: () => api<HistoryItem[]>(`/paths/${path.id}/history`) });
  const exception = useMutation({
    mutationFn: ({ id, step_id, reason }: { id: string; step_id: string; reason: string }) =>
      api(`/path-assignments/${id}/exceptions`, { method: "POST", body: JSON.stringify({ step_id, reason }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paths"] }),
  });
  const ask = (a: Assignment) => {
    const n = window.prompt(`Etapa a dispensar para ${a.student_name} (1-${path.steps.length}):`);
    const step = path.steps[Number(n) - 1];
    if (!step) return;
    const reason = window.prompt("Motivo (mín. 10 caracteres, queda en el historial):");
    if (reason && reason.trim().length >= 10) exception.mutate({ id: a.id, step_id: step.id, reason: reason.trim() });
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <Panel title="Avance de los estudiantes" subtitle="Etapas completadas sobre el total; las dispensadas cuentan como cumplidas">
        {rows.isPending && <Skeleton className="h-40" />}
        {rows.isError && <ErrorState error={rows.error} />}
        {rows.data?.length === 0 && <p className="text-sm text-muted">Aún no hay asignaciones.</p>}
        <ul className="divide-y divide-line">
          {rows.data?.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <span className="min-w-36 flex-1 font-medium">{a.student_name}</span>
              <ProgressBar value={a.progress} className="w-28" />
              <span className="w-16 text-xs text-muted">{a.completed_steps}/{a.total_steps}</span>
              {a.status === "completed" ? <Badge tone="teal">completada</Badge> : a.on_track === false ? <Badge tone="warning">atrasado</Badge> : <Badge tone="muted">a tiempo</Badge>}
              {a.exceptions.length > 0 && <Badge tone="violet" >{a.exceptions.length} excepción</Badge>}
              {can("path.manage") && a.status === "active" && (
                <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => ask(a)}>Excepción</Button>
              )}
            </li>
          ))}
        </ul>
        {exception.isError && <p role="alert" className="mt-2 text-sm text-danger">{err(exception.error)}</p>}
      </Panel>
      <Panel title="Historial" subtitle="Desde la bitácora inmutable" actions={<History className="size-4 text-muted" />}>
        {history.data?.length === 0 && <p className="text-xs text-muted">Sin cambios registrados (ruta cargada como DEMO).</p>}
        <ul className="space-y-2 text-xs">
          {history.data?.map((h, i) => (
            <li key={i}>
              <p><b>{ACTION_LABEL[h.action] ?? h.action}</b> · {h.actor_name ?? "Sistema"}</p>
              <p className="text-muted">{formatDateTime(h.occurred_at)}{h.details?.version ? ` · versión ${String(h.details.version)}` : ""}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function StaffView() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const order = { published: 0, draft: 1, archived: 2 } as const;
  const paths = useQuery({
    queryKey: ["paths", "list"],
    queryFn: async () => (await api<PathOut[]>("/paths")).sort((a, b) => order[a.status] - order[b.status]),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ kind: "new" } | { kind: "edit"; path: PathOut } | { kind: "assign"; path: PathOut } | null>(null);
  const status = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => api(`/paths/${id}/status`, { method: "POST", body: JSON.stringify({ status: value }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paths"] }),
  });
  const current = paths.data?.find((p) => p.id === selected) ?? paths.data?.[0];
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title="Rutas de aprendizaje" description="Secuencias de cursos con objetivo, competencias y prerrequisitos; se asignan por cohorte (§4.2)."
        actions={can("path.manage") && <Button icon={Plus} onClick={() => setDialog({ kind: "new" })}>Nueva ruta</Button>} />
      {paths.isPending && <Skeleton className="h-40" />}
      {paths.isError && <ErrorState error={paths.error} onRetry={() => paths.refetch()} />}
      {paths.data?.length === 0 && <EmptyState icon={Route} title="Sin rutas" description="Crea la primera ruta de la institución." />}
      <div className="grid gap-3 md:grid-cols-2">
        {paths.data?.map((p) => (
          <article key={p.id} className={cx("panel flex cursor-pointer flex-col gap-2 p-4", current?.id === p.id && "panel-glow")} onClick={() => setSelected(p.id)}>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[11px] font-medium text-cyan">{p.code} · v{p.version}</p>
              <Badge tone={p.status === "published" ? "teal" : p.status === "draft" ? "warning" : "muted"}>{STATUS_LABEL[p.status]}</Badge>
              <span className="ml-auto text-xs text-muted">{p.assigned} asignados · {p.completed} completaron</span>
            </div>
            <h3 className="font-semibold">{p.title}</h3>
            <p className="line-clamp-2 text-sm text-muted">{p.objective}</p>
            <p className="text-xs">{p.steps.map((s) => s.course_code + (s.min_grade !== null ? ` (≥${s.min_grade})` : "")).join(" → ")}</p>
            <div className="flex flex-wrap gap-1">{p.competencies.map((c) => <Badge key={c} tone="violet">{c}</Badge>)}</div>
            {can("path.manage") && (
              <div className="mt-1 flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
                {p.status !== "archived" && <Button variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => setDialog({ kind: "edit", path: p })}>Editar</Button>}
                {p.status === "draft" && <Button className="px-2.5 py-1 text-xs" onClick={() => status.mutate({ id: p.id, value: "published" })}>Publicar</Button>}
                {p.status === "published" && <Button variant="ghost" icon={UserPlus} className="px-2.5 py-1 text-xs" onClick={() => setDialog({ kind: "assign", path: p })}>Asignar</Button>}
                {p.status === "published" && <Button variant="ghost" className="px-2.5 py-1 text-xs" onClick={() => status.mutate({ id: p.id, value: "archived" })}>Archivar</Button>}
              </div>
            )}
          </article>
        ))}
      </div>
      {status.isError && <p role="alert" className="text-sm text-danger">{err(status.error)}</p>}
      {current && <PathDetail path={current} />}
      {dialog?.kind === "new" && <PathForm onClose={() => setDialog(null)} />}
      {dialog?.kind === "edit" && <PathForm initial={dialog.path} onClose={() => setDialog(null)} />}
      {dialog?.kind === "assign" && <AssignDialog path={dialog.path} onClose={() => setDialog(null)} />}
    </div>
  );
}

export function PathsPage() {
  const { can } = useAuth();
  const staff = can("path.manage") || can("course.read.all") || can("assessment.manage");
  return staff ? <StaffView /> : <StudentView />;
}
