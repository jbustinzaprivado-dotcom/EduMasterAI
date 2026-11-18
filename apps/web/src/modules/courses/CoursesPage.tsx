import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CalendarPlus, Plus, Trash2, UserPlus, Users, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { ProgressBar } from "../../components/charts";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { LEVEL_LABEL, STATUS_LABEL, type Course, type Offering } from "./api";

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="panel panel-glow flex max-h-[90vh] w-full max-w-xl flex-col gap-4 overflow-y-auto p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Cerrar" className="text-muted hover:text-text"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "No se pudo completar la acción.");

function OfferingCard({ o }: { o: Offering }) {
  const progress = o.my_enrollment?.progress ?? o.avg_progress ?? 0;
  return (
    <Link to={`/cursos/${o.id}`} className="panel group flex flex-col gap-3 p-4 transition-colors hover:border-cyan/50">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium tracking-wide text-cyan">{o.course_code} · {o.cohort} · {o.period}</p>
          <p className="mt-0.5 truncate font-semibold group-hover:text-cyan">{o.course_title}</p>
          <p className="text-xs text-muted">Docente: {o.instructor_name}</p>
        </div>
        <Badge tone="violet">{LEVEL_LABEL[o.course_level] ?? o.course_level}</Badge>
      </div>
      <div>
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>{o.my_enrollment ? "Mi progreso" : "Progreso promedio"}</span>
          <span className="text-text">{Math.round(progress * 100)} %</span>
        </div>
        <ProgressBar value={progress} />
      </div>
      {o.my_enrollment ? (
        <Badge tone={o.my_enrollment.status === "completed" ? "teal" : "cyan"}>{STATUS_LABEL[o.my_enrollment.status]}</Badge>
      ) : (
        <p className="text-xs text-muted">{o.enrolled} matriculados · {o.completed} completaron</p>
      )}
    </Link>
  );
}

function NewCourseDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("basico");
  const [description, setDescription] = useState("");
  const [units, setUnits] = useState([{ title: "", activities: "" }]);
  const save = useMutation({
    mutationFn: () =>
      api<Course>("/courses", {
        method: "POST",
        body: JSON.stringify({
          code, title, level, description,
          units: units.filter((u) => u.title.trim()).map((u) => ({
            title: u.title,
            activities: u.activities.split("\n").map((l) => l.trim()).filter(Boolean).map((t) => ({ title: t })),
          })),
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courses"] });
      onClose();
    },
  });
  return (
    <Dialog title="Nuevo curso" onClose={onClose}>
      <form className="flex flex-col gap-3" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid gap-3 sm:grid-cols-[120px_1fr_140px]">
          <div><label className="label" htmlFor="c-code">Código</label>
            <input id="c-code" className="field uppercase" value={code} onChange={(e) => setCode(e.target.value)} required /></div>
          <div><label className="label" htmlFor="c-title">Título</label>
            <input id="c-title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} /></div>
          <div><label className="label" htmlFor="c-level">Nivel</label>
            <select id="c-level" className="field" value={level} onChange={(e) => setLevel(e.target.value)}>
              {Object.entries(LEVEL_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select></div>
        </div>
        <div><label className="label" htmlFor="c-desc">Descripción</label>
          <textarea id="c-desc" className="field min-h-16" value={description} onChange={(e) => setDescription(e.target.value)} /></div>
        <fieldset className="flex flex-col gap-2">
          <legend className="label">Unidades y actividades (una actividad por línea)</legend>
          {units.map((u, i) => (
            <div key={i} className="rounded-xl border border-line p-3">
              <div className="flex gap-2">
                <input className="field" placeholder={`Unidad ${i + 1}`} aria-label={`Título de la unidad ${i + 1}`} value={u.title}
                  onChange={(e) => setUnits((us) => us.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
                {units.length > 1 && (
                  <Button type="button" variant="ghost" icon={Trash2} aria-label="Quitar unidad"
                    onClick={() => setUnits((us) => us.filter((_, j) => j !== i))} />
                )}
              </div>
              <textarea className="field mt-2 min-h-16" placeholder={"Introducción\nPráctica guiada"} aria-label={`Actividades de la unidad ${i + 1}`}
                value={u.activities} onChange={(e) => setUnits((us) => us.map((x, j) => (j === i ? { ...x, activities: e.target.value } : x)))} />
            </div>
          ))}
          <Button type="button" variant="ghost" icon={Plus} onClick={() => setUnits((us) => [...us, { title: "", activities: "" }])}>
            Agregar unidad
          </Button>
        </fieldset>
        {save.isError && <p role="alert" className="text-sm text-danger">{errText(save.error)}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={save.isPending}>Crear borrador</Button>
        </div>
      </form>
    </Dialog>
  );
}

interface UserLite { id: string; full_name: string; email: string; roles: string[] }

function NewOfferingDialog({ courses, onClose }: { courses: Course[]; onClose: () => void }) {
  const qc = useQueryClient();
  const teachers = useQuery({
    queryKey: ["users", "docente"],
    queryFn: () => api<{ items: UserLite[] }>("/users?role=docente&page_size=100"),
  });
  const today = new Date().toISOString().slice(0, 10);
  const [courseId, setCourseId] = useState("");
  const [instructorId, setInstructorId] = useState("");
  const [period, setPeriod] = useState("2027-I");
  const [cohort, setCohort] = useState("");
  const [starts, setStarts] = useState(today);
  const [ends, setEnds] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api<Offering>("/offerings", {
        method: "POST",
        body: JSON.stringify({
          course_id: courseId, instructor_id: instructorId, period, cohort,
          starts_on: new Date(`${starts}T00:00:00`).toISOString(), ends_on: new Date(`${ends}T23:59:00`).toISOString(),
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings"] });
      onClose();
    },
  });
  const published = courses.filter((c) => c.status === "published");
  return (
    <Dialog title="Nueva oferta de curso" onClose={onClose}>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="sm:col-span-2"><label className="label" htmlFor="o-course">Curso publicado</label>
          <select id="o-course" className="field" value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
            <option value="">Selecciona…</option>
            {published.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}
          </select></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="o-teacher">Docente</label>
          <select id="o-teacher" className="field" value={instructorId} onChange={(e) => setInstructorId(e.target.value)} required>
            <option value="">Selecciona…</option>
            {teachers.data?.items.map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
          </select></div>
        <div><label className="label" htmlFor="o-period">Periodo</label>
          <input id="o-period" className="field" value={period} onChange={(e) => setPeriod(e.target.value)} required /></div>
        <div><label className="label" htmlFor="o-cohort">Cohorte / grupo</label>
          <input id="o-cohort" className="field" value={cohort} onChange={(e) => setCohort(e.target.value)} required placeholder="Grupo C" /></div>
        <div><label className="label" htmlFor="o-start">Inicio</label>
          <input id="o-start" type="date" className="field" value={starts} onChange={(e) => setStarts(e.target.value)} required /></div>
        <div><label className="label" htmlFor="o-end">Fin</label>
          <input id="o-end" type="date" className="field" value={ends} onChange={(e) => setEnds(e.target.value)} required /></div>
        {save.isError && <p role="alert" className="text-sm text-danger sm:col-span-2">{errText(save.error)}</p>}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={save.isPending}>Abrir oferta</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function EnrollDialog({ offering, onClose }: { offering: Offering; onClose: () => void }) {
  const qc = useQueryClient();
  const students = useQuery({
    queryKey: ["users", "estudiante"],
    queryFn: () => api<{ items: UserLite[] }>("/users?role=estudiante&page_size=100"),
  });
  const [selected, setSelected] = useState<string[]>([]);
  const save = useMutation({
    mutationFn: () => api<{ created: number }>(`/offerings/${offering.id}/enrollments`, {
      method: "POST", body: JSON.stringify({ student_ids: selected }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offerings"] });
      qc.invalidateQueries({ queryKey: ["roster", offering.id] });
      onClose();
    },
  });
  return (
    <Dialog title={`Matricular en ${offering.course_title}`} onClose={onClose}>
      {students.isPending && <Skeleton className="h-40" />}
      <ul className="grid max-h-80 gap-1 overflow-y-auto sm:grid-cols-2">
        {students.data?.items.map((s) => (
          <li key={s.id}>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-2.5 py-2 text-sm hover:border-cyan/50">
              <input type="checkbox" className="accent-[var(--color-cyan)]" checked={selected.includes(s.id)}
                onChange={(e) => setSelected((x) => (e.target.checked ? [...x, s.id] : x.filter((i) => i !== s.id)))} />
              {s.full_name}
            </label>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Los ya matriculados se omiten automáticamente.</p>
      {save.isError && <p role="alert" className="text-sm text-danger">{errText(save.error)}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button icon={UserPlus} loading={save.isPending} disabled={!selected.length} onClick={() => save.mutate()}>
          Matricular {selected.length || ""}
        </Button>
      </div>
    </Dialog>
  );
}

function Catalog() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const courses = useQuery({ queryKey: ["courses"], queryFn: () => api<Course[]>("/courses") });
  const [dialog, setDialog] = useState<"course" | "offering" | null>(null);
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api<Course>(`/courses/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });
  return (
    <Panel title="Catálogo de cursos" subtitle="Contenido versionado por estado: borrador → publicado → archivado"
      actions={can("course.manage") && (
        <>
          <Button variant="ghost" icon={CalendarPlus} onClick={() => setDialog("offering")}>Nueva oferta</Button>
          <Button icon={Plus} onClick={() => setDialog("course")}>Nuevo curso</Button>
        </>
      )}>
      {courses.isPending && <Skeleton className="h-40" />}
      {courses.isError && <ErrorState error={courses.error} onRetry={() => courses.refetch()} />}
      {courses.data && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="py-2 pr-3 font-medium">Curso</th><th className="py-2 pr-3 font-medium">Nivel</th>
                <th className="py-2 pr-3 font-medium">Contenido</th><th className="py-2 pr-3 font-medium">Estado</th>
                {can("course.manage") && <th className="py-2 font-medium"><span className="sr-only">Acciones</span></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {courses.data.map((c) => (
                <tr key={c.id}>
                  <td className="py-2.5 pr-3"><p className="font-medium">{c.title}</p><p className="text-xs text-muted">{c.code}</p></td>
                  <td className="py-2.5 pr-3 text-muted">{LEVEL_LABEL[c.level]}</td>
                  <td className="py-2.5 pr-3 text-xs text-muted">{c.unit_count} unidades · {c.activity_count} actividades · {c.offering_count} ofertas</td>
                  <td className="py-2.5 pr-3">
                    <Badge tone={c.status === "published" ? "teal" : c.status === "draft" ? "warning" : "muted"}>{STATUS_LABEL[c.status]}</Badge>
                  </td>
                  {can("course.manage") && (
                    <td className="py-2.5 text-right">
                      {c.status === "draft" && (
                        <Button variant="ghost" className="px-2 py-1 text-xs" loading={setStatus.isPending && setStatus.variables?.id === c.id}
                          onClick={() => setStatus.mutate({ id: c.id, status: "published" })}>Publicar</Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {setStatus.isError && <p role="alert" className="mt-2 text-sm text-danger">{errText(setStatus.error)}</p>}
      {dialog === "course" && <NewCourseDialog onClose={() => setDialog(null)} />}
      {dialog === "offering" && courses.data && <NewOfferingDialog courses={courses.data} onClose={() => setDialog(null)} />}
    </Panel>
  );
}

export function CoursesPage() {
  const { can } = useAuth();
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const student = can("learning") && !can("course.read.all");
  const title = student ? "Mis cursos" : can("course.read.all") ? "Cursos y ofertas" : "Mis ofertas";
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title={title} description={student
        ? "Cursos donde estás matriculado. Tu progreso se calcula con las actividades requeridas completadas."
        : "Ofertas por periodo y cohorte (§4.3). Entra a una para ver contenido, estudiantes y evaluaciones."} />
      <Panel title={student ? "En curso" : "Ofertas"} subtitle={offerings.data ? `${offerings.data.length} visibles para tu rol` : undefined}>
        {offerings.isPending && <Skeleton className="h-40" />}
        {offerings.isError && <ErrorState error={offerings.error} onRetry={() => offerings.refetch()} />}
        {offerings.data?.length === 0 && (
          <EmptyState icon={student ? BookOpen : Users} title="Sin ofertas" description="Aún no hay cursos asignados a tu rol." />
        )}
        <div className={cx("grid gap-3 sm:grid-cols-2 xl:grid-cols-3")}>
          {offerings.data?.map((o) => <OfferingCard key={o.id} o={o} />)}
        </div>
      </Panel>
      {can("course.read.all") && <Catalog />}
    </div>
  );
}
