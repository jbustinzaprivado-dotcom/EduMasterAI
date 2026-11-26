import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Grid3x3, Plus, Sparkles } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Button, cx, EmptyState, ErrorState, PageHeader, Panel, Skeleton, Tabs } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import type { Offering, RosterRow } from "../courses/api";

export const LEVELS = ["principiante", "elemental", "intermedio", "avanzado", "experto"];

interface Heatmap { levels: string[]; engine: string; students: number; rows: { skill_id: string; code: string; name: string; estimated: number[]; validated: number[] }[] }
interface CatalogSkill { id: string; code: string; name: string; description: string; parent_id: string | null; courses: string[] }
interface StudentSkill {
  skill_id: string; code: string; name: string; area: string | null; score: number | null;
  estimated_level: number | null; estimated_label: string | null; validated_level: number | null; validated_label: string | null;
  validated_note: string | null; validated_by: string | null; validated_at: string | null;
  evidences: { source: string; label: string; value: number; weight: number }[];
}

const err = (e: unknown) => (e instanceof ApiError ? e.message : "No se pudo completar la acción.");

export function LevelDots({ level, validated }: { level: number | null; validated?: boolean }) {
  return (
    <span className="inline-flex gap-1" aria-label={level ? `Nivel ${LEVELS[level - 1]}` : "Sin evidencia"}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={cx("size-2.5 rounded-full border",
          level && i <= level ? (validated ? "border-teal bg-teal" : "border-cyan bg-cyan/70") : "border-line bg-transparent")} />
      ))}
    </span>
  );
}

export function HeatmapTable({ data, mode }: { data: Heatmap; mode: "estimated" | "validated" }) {
  const max = Math.max(1, ...data.rows.flatMap((r) => r[mode]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-separate border-spacing-1 text-sm">
        <thead className="text-[11px] text-muted">
          <tr><th className="text-left font-medium">Competencia</th>{data.levels.map((l) => <th key={l} className="font-medium capitalize">{l}</th>)}</tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.skill_id}>
              <td className="pr-2 text-xs"><span className="font-medium">{r.name}</span> <span className="text-muted">{r.code}</span></td>
              {r[mode].map((n, i) => (
                <td key={i} className="h-9 rounded-md text-center text-xs font-semibold"
                  style={{ background: n ? `rgb(${mode === "validated" ? "0 191 166" : "139 77 255"} / ${0.15 + 0.75 * (n / max)})` : "rgb(13 43 82 / 0.5)",
                    color: n / max > 0.5 ? "#06152b" : "#eaf2ff" }}
                  title={`${r.name} · ${data.levels[i]}: ${n} estudiante(s)`}>{n || ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkillCard({ s, children }: { s: StudentSkill; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-40 flex-1 text-sm font-medium">{s.name} <span className="text-xs text-muted">{s.area}</span></p>
        <div className="flex flex-col items-end gap-1 text-[11px]">
          <span className="flex items-center gap-2 text-muted">Estimado (IA, reglas) <LevelDots level={s.estimated_level} /> <span className="w-20 capitalize text-text">{s.estimated_label ?? "sin evidencia"}</span></span>
          <span className="flex items-center gap-2 text-muted">Validado (oficial) <LevelDots level={s.validated_level} validated /> <span className="w-20 capitalize text-text">{s.validated_label ?? "pendiente"}</span></span>
        </div>
      </div>
      {s.validated_note && <p className="mt-1 text-xs text-teal"><BadgeCheck className="inline size-3.5" /> {s.validated_by}: {s.validated_note} · {formatDateTime(s.validated_at)}</p>}
      <button className="mt-1 text-xs text-cyan hover:underline" onClick={() => setOpen((v) => !v)}>{open ? "Ocultar" : "Ver"} evidencias ({s.evidences.length})</button>
      {open && (
        <ul className="mt-1 space-y-0.5 text-xs text-muted">
          {s.evidences.map((e, i) => <li key={i}>{e.source === "evaluacion" ? "Nota oficial" : "Avance de unidad"} · {e.label}: <span className="text-text">{Math.round(e.value * 100)} %</span> (peso {e.weight.toFixed(2)})</li>)}
        </ul>
      )}
      {children}
    </div>
  );
}

function StudentView() {
  const mine = useQuery({ queryKey: ["skills", "mine"], queryFn: () => api<StudentSkill[]>("/my/skills") });
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Mis competencias" description="Nivel estimado a partir de tus notas y avances, y nivel validado por tu docente (el oficial)." />
      {mine.isPending && <Skeleton className="h-64" />}
      {mine.isError && <ErrorState error={mine.error} />}
      {mine.data?.length === 0 && <EmptyState icon={Grid3x3} title="Sin evidencias aún" description="Tus competencias aparecen al avanzar en cursos que las trabajan." />}
      <div className="flex flex-col gap-2">{mine.data?.map((s) => <SkillCard key={s.skill_id} s={s} />)}</div>
      <p className="mt-3 text-[11px] text-muted">El nivel estimado es orientativo (motor de reglas v1); el validado por el docente es el que cuenta (§4.9).</p>
    </div>
  );
}

function StudentDrilldown({ offering }: { offering: Offering }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const roster = useQuery({ queryKey: ["roster", offering.id], queryFn: () => api<RosterRow[]>(`/offerings/${offering.id}/enrollments`) });
  const [studentId, setStudentId] = useState("");
  const skills = useQuery({ queryKey: ["skills", "student", studentId], enabled: !!studentId,
    queryFn: () => api<StudentSkill[]>(`/skills/students/${studentId}`) });
  const validate = useMutation({
    mutationFn: (b: { skill_id: string; level: number; note: string }) =>
      api<StudentSkill[]>("/skills/validations", { method: "POST", body: JSON.stringify({ student_id: studentId, ...b }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["skills"] }); },
  });
  const canValidate = offering.can_manage || can("course.manage");
  return (
    <Panel title="Por estudiante" subtitle="Evidencias, nivel estimado y validación docente">
      <select className="field mb-3 max-w-sm" aria-label="Estudiante" value={studentId} onChange={(e) => setStudentId(e.target.value)}>
        <option value="">Selecciona un estudiante…</option>
        {roster.data?.map((r) => <option key={r.student_id} value={r.student_id}>{r.student_name}</option>)}
      </select>
      {skills.isFetching && <Skeleton className="h-32" />}
      {skills.isError && <ErrorState error={skills.error} />}
      <div className="flex flex-col gap-2">
        {skills.data?.map((s) => (
          <SkillCard key={s.skill_id} s={s}>
            {canValidate && <ValidateForm onSubmit={(level, note) => validate.mutate({ skill_id: s.skill_id, level, note })} busy={validate.isPending} />}
          </SkillCard>
        ))}
      </div>
      {validate.isError && <p role="alert" className="mt-2 text-sm text-danger">{err(validate.error)}</p>}
    </Panel>
  );
}

function ValidateForm({ onSubmit, busy }: { onSubmit: (level: number, note: string) => void; busy: boolean }) {
  const [level, setLevel] = useState("3");
  const [note, setNote] = useState("");
  return (
    <form className="mt-2 flex flex-wrap items-center gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); onSubmit(Number(level), note); setNote(""); }}>
      <select className="field w-36" aria-label="Nivel validado" value={level} onChange={(e) => setLevel(e.target.value)}>
        {LEVELS.map((l, i) => <option key={l} value={i + 1}>{l}</option>)}
      </select>
      <input className="field min-w-48 flex-1" placeholder="Evidencia observada (obligatoria)" aria-label="Nota de validación" value={note} onChange={(e) => setNote(e.target.value)} minLength={5} required />
      <Button type="submit" icon={BadgeCheck} className="px-2.5 py-1.5 text-xs" loading={busy} disabled={note.trim().length < 5}>Validar</Button>
    </form>
  );
}

function Catalog() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const skills = useQuery({ queryKey: ["skills", "catalog"], queryFn: () => api<CatalogSkill[]>("/skills") });
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const create = useMutation({
    mutationFn: () => api("/skills", { method: "POST", body: JSON.stringify({ code, name, parent_id: parent || null }) }),
    onSuccess: () => { setCode(""); setName(""); qc.invalidateQueries({ queryKey: ["skills"] }); },
  });
  const areas = skills.data?.filter((s) => !s.parent_id) ?? [];
  return (
    <Panel title="Catálogo de competencias" subtitle="Dos niveles: área → competencia">
      <ul className="space-y-2 text-sm">
        {areas.map((a) => (
          <li key={a.id}>
            <p className="font-semibold">{a.name} <span className="text-xs text-muted">{a.code}</span></p>
            <ul className="mt-1 ml-3 space-y-0.5 text-xs">
              {skills.data?.filter((s) => s.parent_id === a.id).map((s) => (
                <li key={s.id} className="flex justify-between gap-2"><span>{s.name}</span><span className="text-muted">{s.courses.join(", ") || "sin curso"}</span></li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      {can("course.manage") && (
        <form className="mt-4 grid gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
          <div className="grid grid-cols-[100px_1fr] gap-2">
            <input className="field uppercase" placeholder="Código" aria-label="Código" value={code} onChange={(e) => setCode(e.target.value)} />
            <input className="field" placeholder="Nombre" aria-label="Nombre" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <select className="field" aria-label="Área" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">Nueva área (sin padre)</option>
            {areas.map((a) => <option key={a.id} value={a.id}>Competencia de: {a.name}</option>)}
          </select>
          {create.isError && <p role="alert" className="text-xs text-danger">{err(create.error)}</p>}
          <Button type="submit" icon={Plus} className="justify-self-end px-2.5 py-1.5 text-xs" loading={create.isPending} disabled={code.length < 2 || name.length < 3}>Agregar</Button>
        </form>
      )}
    </Panel>
  );
}

function StaffView() {
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const [offeringId, setOfferingId] = useState("");
  const [mode, setMode] = useState<"estimated" | "validated">("estimated");
  const heat = useQuery({
    queryKey: ["skills", "heatmap", offeringId],
    queryFn: () => api<Heatmap>(`/analytics/skill-mastery${offeringId ? `?offering_id=${offeringId}` : ""}`),
  });
  const offering = offerings.data?.find((o) => o.id === offeringId);
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader title="Dominio de habilidades" description="Heatmap por competencia y nivel; el nivel estimado se muestra separado del validado por el docente (§4.9)." />
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted" htmlFor="skills-offering">Oferta</label>
        <select id="skills-offering" className="field w-64" value={offeringId} onChange={(e) => setOfferingId(e.target.value)}>
          <option value="">Todas mis ofertas</option>
          {offerings.data?.map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.cohort}</option>)}
        </select>
      </div>
      <Tabs label="Secciones de habilidades" param="seccion" items={[
        { id: "mapa", label: "Mapa de calor", content: (
          <Panel title="Heatmap" subtitle={heat.data ? `${heat.data.students} estudiantes · motor ${heat.data.engine}` : undefined}
            actions={
              <div className="flex rounded-[10px] border border-line text-xs">
                {(["estimated", "validated"] as const).map((m) => (
                  <button key={m} onClick={() => setMode(m)} className={cx("px-3 py-1.5", mode === m ? "bg-primary/20 text-cyan" : "text-muted")}>
                    {m === "estimated" ? "Estimado" : "Validado"}
                  </button>
                ))}
              </div>
            }>
            {heat.isPending && <Skeleton className="h-64" />}
            {heat.isError && <ErrorState error={heat.error} />}
            {heat.data && (heat.data.rows.length ? <HeatmapTable data={heat.data} mode={mode} /> :
              <EmptyState icon={Grid3x3} title="Sin competencias vinculadas" description="Vincula competencias a los cursos desde el catálogo." />)}
            <p className="mt-2 flex items-center gap-1 text-[11px] text-muted"><Sparkles className="size-3" /> Estimado = reglas sobre notas oficiales y avance por unidad (orientativo). Validado = decisión del docente (oficial).</p>
          </Panel>
        ) },
        { id: "estudiantes", label: "Por estudiante y validación", content: offering
          ? <StudentDrilldown offering={offering} />
          : <p className="text-sm text-muted">Elige una oferta arriba para ver y validar competencias por estudiante.</p> },
        { id: "catalogo", label: "Catálogo", content: <Catalog /> },
      ]} />
    </div>
  );
}

export function SkillsPage() {
  const { can } = useAuth();
  return can("analytics.read") ? <StaffView /> : <StudentView />;
}
