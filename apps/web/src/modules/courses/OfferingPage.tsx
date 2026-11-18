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
        <p className={cx("text-sm", done && "text-muted line-through decoration-teal/50")}>{activity.title}</p>
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

function Roster({ offering }: { offering: Offering }) {
  const roster = useQuery({
    queryKey: ["roster", offering.id],
    queryFn: () => api<RosterRow[]>(`/offerings/${offering.id}/enrollments`),
  });
  if (roster.isPending) return <Skeleton className="h-48" />;
  if (roster.isError) return <ErrorState error={roster.error} onRetry={() => roster.refetch()} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] text-left text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">Estudiante</th><th className="py-2 pr-3 font-medium">Progreso</th>
            <th className="py-2 pr-3 font-medium">Última actividad</th><th className="py-2 pr-3 font-medium">Nota oficial (0-20)</th>
            <th className="py-2 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {roster.data.map((r) => {
            const inactiveDays = r.last_activity_at ? (Date.now() - new Date(r.last_activity_at).getTime()) / 86_400_000 : 99;
            return (
              <tr key={r.enrollment_id}>
                <td className="py-2.5 pr-3"><p className="font-medium">{r.student_name}</p><p className="text-xs text-muted">{r.student_email}</p></td>
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
      <p className="mt-3 text-[11px] text-muted">
        En ámbar: más de 10 días sin actividad. Es un dato observado, no una predicción; la alerta de riesgo con IA llega en la Fase 5.
      </p>
    </div>
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
      {enrolling && <EnrollDialog offering={o} onClose={() => setEnrolling(false)} />}
    </div>
  );
}
