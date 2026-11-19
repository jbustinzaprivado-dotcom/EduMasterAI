import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BarChart3, Download, FileSpreadsheet, FileText, Info } from "lucide-react";
import { useState } from "react";
import { TrendChart } from "../../components/charts";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";
import { ApiError, api, apiBlob } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

interface Definition { label: string; unit: string; definition: string }
type Summary = Record<string, number | null>;
type OfferingRow = Summary;
interface Overview {
  generated_at: string;
  filters: Record<string, string>;
  definitions: Record<string, Definition>;
  options: { offerings: { id: string; label: string }[]; cohorts: string[]; periods: string[]; instructors: [string, string][] };
  students_visible: boolean;
  totals: Summary;
  by_offering: (OfferingRow & { offering_id: string; course_code: string; course_title: string; cohort: string; period: string; instructor: string })[];
  students: { student_name: string; course_code: string; cohort: string; active_days: number; active_hours: number; submissions: number;
    late_submissions: number; progress: number; status: string; grade: number | null; last_activity_at: string | null }[] | null;
  weekly: { week_start: string; active_students: number; hours: number; submissions: number }[];
}

const KPIS = ["participation_rate", "active_hours", "avg_active_days", "submissions", "on_time_rate",
  "attempts_per_assessment", "avg_progress", "completion_rate", "avg_grade"];

function fmt(unit: string, v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (unit === "%") return `${Math.round(v * 1000) / 10} %`;
  if (unit === "/20") return v.toFixed(1);
  return String(v);
}

const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);

export function AnalyticsPage() {
  const [from, setFrom] = useState(daysAgo(30));
  const [to, setTo] = useState(today());
  const [offering, setOffering] = useState("");
  const [cohort, setCohort] = useState("");
  const [instructor, setInstructor] = useState("");
  const [period, setPeriod] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const params = new URLSearchParams({
    date_from: new Date(`${from}T00:00:00`).toISOString(),
    date_to: new Date(`${to}T23:59:59`).toISOString(),
  });
  if (offering) params.set("offering_id", offering);
  if (cohort) params.set("cohort", cohort);
  if (instructor) params.set("instructor_id", instructor);
  if (period) params.set("period", period);

  const data = useQuery({
    queryKey: ["analytics", params.toString()],
    queryFn: () => api<Overview>(`/analytics/overview?${params}`),
    placeholderData: keepPreviousData,
  });

  async function download(format: "csv" | "xlsx" | "pdf", level: "offerings" | "students") {
    setExporting(`${format}-${level}`);
    setExportError(null);
    try {
      const blob = await apiBlob(`/analytics/export?${params}&format=${format}&level=${level}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `edumaster-analitica-${level}.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setExportError(e instanceof ApiError ? e.message : "No se pudo exportar.");
    } finally {
      setExporting(null);
    }
  }

  const d = data.data;
  const fmtWeek = new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short" });

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4">
      <PageHeader title="Analítica educativa" description="Indicadores con definición documentada, filtros y exportación auditada (§4.4)." />

      <Panel title="Filtros" subtitle="Se aplican a los indicadores, tablas y exportaciones">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div><label className="label" htmlFor="f-from">Desde</label><input id="f-from" type="date" className="field" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
          <div><label className="label" htmlFor="f-to">Hasta</label><input id="f-to" type="date" className="field" value={to} onChange={(e) => setTo(e.target.value)} /></div>
          <div><label className="label" htmlFor="f-off">Oferta</label>
            <select id="f-off" className="field" value={offering} onChange={(e) => setOffering(e.target.value)}>
              <option value="">Todas</option>{d?.options.offerings.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select></div>
          <div><label className="label" htmlFor="f-coh">Cohorte</label>
            <select id="f-coh" className="field" value={cohort} onChange={(e) => setCohort(e.target.value)}>
              <option value="">Todas</option>{d?.options.cohorts.map((c) => <option key={c}>{c}</option>)}
            </select></div>
          <div><label className="label" htmlFor="f-ins">Docente</label>
            <select id="f-ins" className="field" value={instructor} onChange={(e) => setInstructor(e.target.value)}>
              <option value="">Todos</option>{d?.options.instructors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select></div>
          <div><label className="label" htmlFor="f-per">Periodo</label>
            <select id="f-per" className="field" value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="">Todos</option>{d?.options.periods.map((p) => <option key={p}>{p}</option>)}
            </select></div>
        </div>
      </Panel>

      {data.isPending && <Skeleton className="h-64" />}
      {data.isError && <ErrorState error={data.error} onRetry={() => data.refetch()} />}
      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
            {KPIS.map((k) => {
              const def = d.definitions[k]!;
              return (
                <div key={k} className="panel flex flex-col gap-1 p-3" title={def.definition}>
                  <p className="flex items-center gap-1 text-[11px] text-muted">{def.label} <Info className="size-3" aria-hidden /></p>
                  <p className="text-xl font-semibold">{fmt(def.unit, d.totals[k])}</p>
                  <p className="text-[10px] text-muted">{def.unit !== "%" && def.unit !== "/20" ? def.unit : ""}</p>
                </div>
              );
            })}
          </div>
          <p className="-mt-2 text-[11px] text-muted">
            {d.totals.enrolled} matrículas vigentes · Generado {formatDateTime(d.generated_at)} · Pasa el cursor sobre un indicador para ver su definición.
          </p>

          <Panel title="Tendencia semanal" subtitle="Estudiantes activos, horas y entregas dentro del rango">
            {d.weekly.every((w) => !w.active_students && !w.submissions) ? (
              <EmptyState icon={BarChart3} title="Sin actividad en el rango" description="Amplía las fechas o quita filtros." />
            ) : (
              <TrendChart labels={d.weekly.map((w) => fmtWeek.format(new Date(w.week_start)))} series={[
                { key: "s", label: "Estudiantes activos", unit: "est.", color: "#8b4dff", values: d.weekly.map((w) => w.active_students) },
                { key: "h", label: "Horas", unit: "h", color: "#00bfa6", values: d.weekly.map((w) => w.hours) },
                { key: "e", label: "Entregas", unit: "ent.", color: "#20c8f5", values: d.weekly.map((w) => w.submissions) },
              ]} />
            )}
          </Panel>

          <Panel title="Por oferta" subtitle="Curso, cohorte y docente"
            actions={
              <div className="flex flex-wrap gap-1.5">
                <Button variant="ghost" icon={FileText} className="px-2.5 py-1 text-xs" loading={exporting === "csv-offerings"} onClick={() => download("csv", "offerings")}>CSV</Button>
                <Button variant="ghost" icon={FileSpreadsheet} className="px-2.5 py-1 text-xs" loading={exporting === "xlsx-offerings"} onClick={() => download("xlsx", "offerings")}>XLSX</Button>
                <Button variant="ghost" icon={Download} className="px-2.5 py-1 text-xs" loading={exporting === "pdf-offerings"} onClick={() => download("pdf", "offerings")}>PDF</Button>
              </div>
            }>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3 font-medium">Oferta</th><th className="py-2 pr-3 font-medium">Docente</th>
                    <th className="py-2 pr-3 font-medium">Matr.</th>
                    {["participation_rate", "active_hours", "on_time_rate", "avg_progress", "completion_rate", "avg_grade"].map((k) => (
                      <th key={k} className="py-2 pr-3 font-medium" title={d.definitions[k]!.definition}>{d.definitions[k]!.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {d.by_offering.map((r) => (
                    <tr key={r.offering_id}>
                      <td className="py-2 pr-3"><p className="font-medium">{r.course_code} · {r.cohort}</p><p className="text-xs text-muted">{r.course_title} · {r.period}</p></td>
                      <td className="py-2 pr-3 text-xs">{r.instructor}</td>
                      <td className="py-2 pr-3">{r.enrolled}</td>
                      {["participation_rate", "active_hours", "on_time_rate", "avg_progress", "completion_rate", "avg_grade"].map((k) => (
                        <td key={k} className="py-2 pr-3">{fmt(d.definitions[k]!.unit, r[k])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {d.students_visible && d.students ? (
            <Panel title="Por estudiante" subtitle="Detalle nominal: visible para gestión, docentes (sus ofertas) y auditoría"
              actions={
                <div className="flex flex-wrap gap-1.5">
                  <Button variant="ghost" icon={FileText} className="px-2.5 py-1 text-xs" loading={exporting === "csv-students"} onClick={() => download("csv", "students")}>CSV</Button>
                  <Button variant="ghost" icon={FileSpreadsheet} className="px-2.5 py-1 text-xs" loading={exporting === "xlsx-students"} onClick={() => download("xlsx", "students")}>XLSX</Button>
                  <Button variant="ghost" icon={Download} className="px-2.5 py-1 text-xs" loading={exporting === "pdf-students"} onClick={() => download("pdf", "students")}>PDF</Button>
                </div>
              }>
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="sticky top-0 bg-surface text-xs text-muted">
                    <tr className="border-b border-line">
                      <th className="py-2 pr-3 font-medium">Estudiante</th><th className="py-2 pr-3 font-medium">Curso</th>
                      <th className="py-2 pr-3 font-medium">Días activos</th><th className="py-2 pr-3 font-medium">Horas</th>
                      <th className="py-2 pr-3 font-medium">Entregas (tardías)</th><th className="py-2 pr-3 font-medium">Progreso</th>
                      <th className="py-2 pr-3 font-medium">Nota</th><th className="py-2 font-medium">Última actividad</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {d.students.map((s, i) => (
                      <tr key={i}>
                        <td className="py-2 pr-3">{s.student_name}</td>
                        <td className="py-2 pr-3 text-xs">{s.course_code} · {s.cohort}</td>
                        <td className="py-2 pr-3">{s.active_days}</td>
                        <td className="py-2 pr-3">{s.active_hours}</td>
                        <td className="py-2 pr-3">{s.submissions}{s.late_submissions ? <span className="text-warning"> ({s.late_submissions})</span> : ""}</td>
                        <td className="py-2 pr-3">{Math.round(s.progress * 100)} %{s.status === "completed" && <Badge tone="teal">completó</Badge>}</td>
                        <td className="py-2 pr-3">{s.grade !== null ? s.grade.toFixed(1) : "—"}</td>
                        <td className="py-2 text-xs text-muted">{formatDateTime(s.last_activity_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          ) : (
            <p className="text-xs text-muted">Tu rol ve solo agregados: el detalle por estudiante no está disponible (§3).</p>
          )}
          {exportError && <p role="alert" className="text-sm text-danger">{exportError}</p>}
          <p className="text-[11px] text-muted">Cada exportación incluye fecha y filtros en el encabezado y queda registrada en la bitácora.</p>
        </>
      )}
    </div>
  );
}
