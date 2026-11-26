import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpenText, CheckCircle2, Circle, Code2, PlayCircle, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { ProgressBar } from "../../components/charts";
import { Badge, Button, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime, relativeTime } from "../../lib/format";
import { KIND_LABEL, LEVEL_LABEL, STATUS_LABEL, sendEvent, type Activity, type Offering, type RosterRow } from "./api";
import { EnrollDialog } from "./CoursesPage";
import { KIND_META, STATUS_TONE, type Recommendation } from "../recommendations/RecommendationCard";

const KIND_ICON = { lectura: BookOpenText, video: PlayCircle, practica: Code2 };

function ActivityRow({ offering, activity, done }: { offering: Offering; activity: Activity; done: boolean }) {
  const qc = useQueryClient();
  const student = !!offering.my_enrollment;
  const complete = useMutation({
    mutationFn: async () => {
      await sendEvent(offering.id, "lesson_viewed", activity.id, activity.estimated_minutes * 60);
      return sendEvent(offering.id, "activity_completed", activity.id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offering", offering.id] });
      qc.invalidateQueries({ queryKey: ["offerings"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const Icon = KIND_ICON[activity.kind];
  return (
    <li className="flex flex-wrap items-center gap-3 py-2.5">
      {student ? (done ? <CheckCircle2 className="size-5 text-teal" aria-label="Completada" /> : <Circle className="size-5 text-muted/60" aria-label="Pendiente" />)
        : <Icon className="size-5 text-cyan" aria-hidden />}
      <div className="min-w-0 flex-1">
        <Link to={`/cursos/${offering.id}/actividad/${activity.id}`} className={cx("text-sm hover:text-cyan hover:underline", done && "text-muted line-through decoration-teal/50")}>{activity.title}</Link>
        <p className="text-xs text-muted">{KIND_LABEL[activity.kind]} · {activity.estimated_minutes} min{activity.required ? "" : " · opcional"}</p>
      </div>
      {student && !done && offering.my_enrollment?.status !== "dropped" && (
        <Button variant="ghost" className="px-2.5 py-1 text-xs" loading={complete.isPending} onClick={() => complete.mutate()}>
          Marcar como completada
        </Button>
      )}
      {complete.isError && <p role="alert" className="w-full text-xs text-danger">{complete.error instanceof ApiError ? complete.error.message : "Error"}</p>}
    </li>
  );
}

interface Risk {
  prediction_id: string;
  enrollment_id: string;
  score: number;
  risk_level: "alto" | "medio" | "bajo";
  factors: { feature: string; label: string; impact: number }[];
  model_version: string;
  created_at: string;
  review_status: "pendiente" | "atendida" | "descartada";
  review_note: string | null;
}

const RISK_TONE = { alto: "danger", medio: "warning", bajo: "teal" } as const;

function RiskCell({ risk, canReview, offeringId }: { risk: Risk | undefined; canReview: boolean; offeringId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const review = useMutation({
    mutationFn: ({ status, note }: { status: string; note?: string }) =>
      api<Risk>(`/ml/predictions/${risk!.prediction_id}/review`, { method: "PATCH", body: JSON.stringify({ status, note }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk", offeringId] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
    },
  });
  if (!risk) return <span className="text-xs text-muted">—</span>;
  return (
    <div className="relative">
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-1.5" aria-expanded={open}
        aria-label={`Riesgo ${risk.risk_level}, ${Math.round(risk.score * 100)} %. Ver detalle`}>
        <Badge tone={RISK_TONE[risk.risk_level]}>{risk.risk_level} · {Math.round(risk.score * 100)} %</Badge>
        {risk.review_status !== "pendiente" && <Badge tone="muted">{risk.review_status}</Badge>}
      </button>
      {open && (
        <div className="panel panel-solid absolute left-0 z-20 mt-2 w-72 p-3 text-xs">
          <p className="font-semibold">Estimación del modelo v{risk.model_version}</p>
          <p className="mt-0.5 text-muted">Probabilidad de 14 días sin actividad. Es un apoyo, no un diagnóstico (§9.8).</p>
          {risk.factors.length > 0 ? (
            <ul className="mt-2 list-inside list-disc space-y-0.5">
              {risk.factors.map((f) => <li key={f.feature}>{f.label} <span className="text-muted">(+{Math.round(f.impact * 100)} pts)</span></li>)}
            </ul>
          ) : <p className="mt-2 text-muted">Sin factores destacados.</p>}
          {risk.review_note && <p className="mt-2 text-muted">Nota: {risk.review_note}</p>}
          <Link to={`/red-neuronal?oferta=${offeringId}&matricula=${risk.enrollment_id}`}
            className="mt-2 inline-block text-cyan hover:underline">Ver su recorrido en la red neuronal →</Link>
          {canReview && risk.review_status === "pendiente" && risk.risk_level !== "bajo" && (
            <div className="mt-3 flex gap-2">
              <Button className="px-2 py-1 text-xs" loading={review.isPending}
                onClick={() => review.mutate({ status: "atendida", note: "Contactado por el docente" })}>Marcar atendida</Button>
              <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => {
                const note = window.prompt("¿Por qué descartas la alerta? (sirve para evaluar el modelo)");
                if (note?.trim()) review.mutate({ status: "descartada", note });
              }}>Descartar</Button>
            </div>
          )}
          {review.isError && <p role="alert" className="mt-2 text-danger">{review.error instanceof ApiError ? review.error.message : "Error"}</p>}
        </div>
      )}
    </div>
  );
}

function Roster({ offering }: { offering: Offering }) {
  const qc = useQueryClient();
  const roster = useQuery({
    queryKey: ["roster", offering.id],
    queryFn: () => api<RosterRow[]>(`/offerings/${offering.id}/enrollments`),
  });
  const risk = useQuery({ queryKey: ["risk", offering.id], queryFn: () => api<Risk[]>(`/ml/offerings/${offering.id}/risk`) });
  const run = useMutation({
    mutationFn: () => api("/ml/predictions/run", { method: "POST", body: JSON.stringify({ offering_id: offering.id }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk", offering.id] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["ml"] });
    },
  });
  if (roster.isPending) return <Skeleton className="h-48" />;
  if (roster.isError) return <ErrorState error={roster.error} onRetry={() => roster.refetch()} />;
  const byEnrollment = new Map((risk.data ?? []).map((r) => [r.enrollment_id, r]));
  const order = { alto: 0, medio: 1, bajo: 2 };
  const rank = (id: string) => order[byEnrollment.get(id)?.risk_level ?? "bajo"];
  const rows = [...roster.data].sort((a, b) => rank(a.enrollment_id) - rank(b.enrollment_id) || a.student_name.localeCompare(b.student_name));
  const lastRun = risk.data?.[0]?.created_at;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{lastRun ? `Riesgo calculado ${relativeTime(lastRun)}` : "Aún no hay predicciones de riesgo para esta oferta."}</span>
        {offering.can_manage && (
          <Button variant="ghost" className="ml-auto px-2.5 py-1 text-xs" loading={run.isPending} onClick={() => run.mutate()}>
            Actualizar riesgo con IA
          </Button>
        )}
      </div>
      {run.isError && <p role="alert" className="mb-2 text-sm text-danger">{run.error instanceof ApiError ? run.error.message : "Error"}</p>}
      <div className="overflow-x-auto pb-40">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th className="py-2 pr-3 font-medium">Estudiante</th><th className="py-2 pr-3 font-medium">Riesgo (IA)</th>
              <th className="py-2 pr-3 font-medium">Progreso</th><th className="py-2 pr-3 font-medium">Última actividad</th>
              <th className="py-2 pr-3 font-medium">Nota oficial (0-20)</th><th className="py-2 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => {
              const inactiveDays = r.last_activity_at ? (Date.now() - new Date(r.last_activity_at).getTime()) / 86_400_000 : 99;
              return (
                <tr key={r.enrollment_id}>
                  <td className="py-2.5 pr-3"><p className="font-medium">{r.student_name}</p><p className="text-xs text-muted">{r.student_email}</p></td>
                  <td className="py-2.5 pr-3"><RiskCell risk={byEnrollment.get(r.enrollment_id)} canReview={offering.can_manage} offeringId={offering.id} /></td>
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-2"><ProgressBar value={r.progress} className="w-24" />
                      <span className="text-xs text-muted">{Math.round(r.progress * 100)} %</span></div>
                  </td>
                  <td className={cx("py-2.5 pr-3 text-xs", inactiveDays > 10 ? "text-warning" : "text-muted")}
                    title={formatDateTime(r.last_activity_at)}>
                    {r.last_activity_at ? relativeTime(r.last_activity_at) : "Sin actividad"}
                  </td>
                  <td className="py-2.5 pr-3">
                    {r.grade !== null ? (
                      <span className={cx("font-semibold", r.grade < 11 ? "text-danger" : "text-text")}>{r.grade.toFixed(1)}</span>
                    ) : <span className="text-muted">—</span>}
                    {r.graded_weight > 0 && <span className="ml-1 text-[11px] text-muted">({Math.round(r.graded_weight * 100)} % evaluado)</span>}
                  </td>
                  <td className="py-2.5"><Badge tone={r.status === "completed" ? "teal" : r.status === "dropped" ? "danger" : "cyan"}>{STATUS_LABEL[r.status]}</Badge></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted">
        Riesgo (IA): probabilidad estimada de pasar 14 días sin actividad, con un modelo entrenado solo con datos DEMO
        sintéticos. Es una alerta de apoyo para el docente: no califica ni sanciona (§9.8). El estudiante no ve este puntaje.
      </p>
    </div>
  );
}

interface EligibilityRow {
  enrollment_id: string;
  student_name: string;
  progress: number;
  eligible: boolean;
  reason: string;
  final_grade: number | null;
  certificate: { id: string; folio: string; status: string } | null;
}

function OfferingCertificates({ offering }: { offering: Offering }) {
  const qc = useQueryClient();
  const rows = useQuery({
    queryKey: ["certificates", "offering", offering.id],
    queryFn: () => api<EligibilityRow[]>(`/certificates/offerings/${offering.id}`),
  });
  const issue = useMutation({
    mutationFn: (enrollment_id: string) => api("/certificates", { method: "POST", body: JSON.stringify({ enrollment_id }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["certificates"] }),
  });
  const issued = rows.data?.filter((r) => r.certificate).length ?? 0;
  return (
    <Panel title="Certificados" subtitle={`Criterio oficial (D29): curso completo, nota ≥ 11 y ≥ 50 % del peso calificado · ${issued} emitidos`}>
      {rows.isPending && <Skeleton className="h-32" />}
      {rows.isError && <ErrorState error={rows.error} onRetry={() => rows.refetch()} />}
      <ul className="divide-y divide-line">
        {rows.data?.map((r) => (
          <li key={r.enrollment_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="min-w-40 flex-1 font-medium">{r.student_name}</span>
            {r.certificate ? (
              <Badge tone={r.certificate.status === "emitido" ? "teal" : "danger"}>{r.certificate.folio}</Badge>
            ) : r.eligible ? (
              <Button className="px-2.5 py-1 text-xs" loading={issue.isPending && issue.variables === r.enrollment_id}
                onClick={() => issue.mutate(r.enrollment_id)}>Emitir</Button>
            ) : (
              <span className="text-xs text-muted">{r.reason}</span>
            )}
          </li>
        ))}
      </ul>
      {issue.isError && <p role="alert" className="mt-2 text-sm text-danger">{issue.error instanceof ApiError ? issue.error.message : "Error"}</p>}
    </Panel>
  );
}

function GroupRecommendations({ offering }: { offering: Offering }) {
  const recs = useQuery({
    queryKey: ["recommendations", "offering", offering.id],
    queryFn: () => api<Recommendation[]>(`/offerings/${offering.id}/recommendations`),
  });
  const open = recs.data?.filter((r) => r.status === "nueva" || r.status === "aceptada") ?? [];
  return (
    <Panel title="Recomendaciones del grupo" subtitle="Lo que el motor sugiere a cada estudiante (§4.5). Tu criterio prevalece.">
      {recs.isPending && <Skeleton className="h-32" />}
      {recs.isError && <ErrorState error={recs.error} onRetry={() => recs.refetch()} />}
      {recs.data && (open.length === 0 ? <p className="text-sm text-muted">No hay sugerencias vigentes.</p> : (
        <ul className="divide-y divide-line">
          {open.map((r) => (
            <li key={r.id} className="flex flex-wrap items-start gap-3 py-2.5 text-sm">
              <Badge tone={KIND_META[r.kind].tone}>{KIND_META[r.kind].label}</Badge>
              <div className="min-w-0 flex-1">
                <p><span className="font-medium">{r.student_name}</span> · {r.title}</p>
                <p className="text-xs text-muted">{r.reason}</p>
              </div>
              <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
            </li>
          ))}
        </ul>
      ))}
    </Panel>
  );
}

export function OfferingPage() {
  const { offeringId = "" } = useParams();
  const { can } = useAuth();
  const [enrolling, setEnrolling] = useState(false);
  const offering = useQuery({ queryKey: ["offering", offeringId], queryFn: () => api<Offering>(`/offerings/${offeringId}`) });

  if (offering.isPending) return <Skeleton className="mx-auto h-96 max-w-6xl" />;
  if (offering.isError) return <div className="mx-auto max-w-xl"><ErrorState error={offering.error} onRetry={() => offering.refetch()} /></div>;
  const o = offering.data;
  const done = new Set(o.my_enrollment?.completed_activity_ids ?? []);
  const showRoster = o.can_manage || can("audit.read");

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <Link to="/cursos" className="inline-flex items-center gap-1 text-xs text-muted hover:text-cyan"><ArrowLeft className="size-3.5" /> Volver a cursos</Link>
      <PageHeader title={o.course_title}
        description={`${o.course_code} · ${LEVEL_LABEL[o.course_level]} · ${o.cohort} · ${o.period} · Docente: ${o.instructor_name}`}
        actions={can("course.manage") && <Button icon={UserPlus} variant="ghost" onClick={() => setEnrolling(true)}>Matricular</Button>} />

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <Panel title="Contenido" subtitle="Unidades y actividades del curso">
          <ol className="flex flex-col gap-4">
            {o.units?.map((u) => (
              <li key={u.id}>
                <p className="text-xs font-semibold tracking-wide text-cyan uppercase">Unidad {u.position} · {u.title}</p>
                <ul className="divide-y divide-line">
                  {u.activities.map((a) => <ActivityRow key={a.id} offering={o} activity={a} done={done.has(a.id)} />)}
                </ul>
              </li>
            ))}
          </ol>
        </Panel>
        <div className="flex flex-col gap-4">
          <Panel title={o.my_enrollment ? "Mi avance" : "Resumen de la oferta"}>
            {o.my_enrollment ? (
              <div className="flex flex-col gap-2">
                <p className="text-3xl font-semibold">{Math.round(o.my_enrollment.progress * 100)} %</p>
                <ProgressBar value={o.my_enrollment.progress} />
                <Badge tone={o.my_enrollment.status === "completed" ? "teal" : "cyan"}>{STATUS_LABEL[o.my_enrollment.status]}</Badge>
                <p className="text-xs text-muted">Progreso = actividades requeridas completadas / total (§4.4).</p>
              </div>
            ) : (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-muted">Matriculados</dt><dd className="text-xl font-semibold">{o.enrolled}</dd></div>
                <div><dt className="text-xs text-muted">Completaron</dt><dd className="text-xl font-semibold">{o.completed}</dd></div>
                <div className="col-span-2"><dt className="mb-1 text-xs text-muted">Progreso promedio</dt>
                  <dd><ProgressBar value={o.avg_progress ?? 0} /><span className="text-xs text-muted">{Math.round((o.avg_progress ?? 0) * 100)} %</span></dd></div>
              </dl>
            )}
          </Panel>
          <Panel title="Evaluaciones">
            <p className="text-sm text-muted">Entregas, notas y rúbricas de esta oferta.</p>
            <Link to="/evaluaciones" className="mt-2 text-sm text-cyan hover:underline">Ir a evaluaciones →</Link>
          </Panel>
        </div>
      </div>

      {showRoster && <Panel title="Estudiantes" subtitle="Progreso, última actividad y nota oficial ponderada"><Roster offering={o} /></Panel>}
      {showRoster && <GroupRecommendations offering={o} />}
      {showRoster && <OfferingCertificates offering={o} />}
      {enrolling && <EnrollDialog offering={o} onClose={() => setEnrolling(false)} />}
    </div>
  );
}
