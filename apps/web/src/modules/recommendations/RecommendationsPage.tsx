import { useQuery } from "@tanstack/react-query";
import { AlarmClock, ArrowRight, Bot, ClipboardCheck, Gauge, ShieldAlert, Sparkles, UserX } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { TrendChart } from "../../components/charts";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, Tabs, type TabItem } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Offering } from "../courses/api";
import { KIND_META, RecommendationCard, STATUS_TONE, type Recommendation } from "./RecommendationCard";

interface KindMetrics {
  kind: keyof typeof KIND_META;
  total: number;
  nueva: number;
  aceptada: number;
  completada: number;
  descartada: number;
  expirada: number;
  acceptance_rate: number | null;
  useful_rate: number | null;
}

interface TeacherAction {
  kind: "por_calificar" | "alertas" | "sin_entregar" | "inactivos" | "competencia_grupo";
  offering_id: string;
  course: string;
  title: string;
  reason: string;
  count: number;
  link: string;
  priority: number;
}

interface Insights {
  weekly: { week_start: string; generated: number; accepted: number; completed: number; discarded: number }[];
  by_course: { course: string; total: number; acceptance_rate: number | null; useful_rate: number | null }[];
  discard_reasons: { reason: string; count: number }[];
}

const ACTION_META: Record<TeacherAction["kind"], { icon: typeof Bot; tone: "danger" | "warning" | "cyan" | "violet" | "teal"; cta: string }> = {
  alertas: { icon: ShieldAlert, tone: "danger", cta: "Revisar alertas" },
  por_calificar: { icon: ClipboardCheck, tone: "warning", cta: "Calificar" },
  sin_entregar: { icon: AlarmClock, tone: "warning", cta: "Enviar recordatorio" },
  inactivos: { icon: UserX, tone: "violet", cta: "Ver estudiantes" },
  competencia_grupo: { icon: Gauge, tone: "cyan", cta: "Ver el mapa de calor" },
};

const pct = (x: number | null) => (x === null ? "—" : `${Math.round(x * 100)} %`);

export function useMyRecommendations(offeringId?: string, history = false, enabled = true) {
  const params = new URLSearchParams();
  if (offeringId) params.set("offering_id", offeringId);
  if (history) params.set("history", "true");
  return useQuery({
    queryKey: ["recommendations", offeringId ?? "all", history],
    queryFn: () => api<Recommendation[]>(`/recommendations?${params}`),
    enabled,
  });
}

export function MetricsTable() {
  const metrics = useQuery({ queryKey: ["recommendations", "metrics"], queryFn: () => api<KindMetrics[]>("/recommendations/metrics") });
  if (metrics.isPending) return <Skeleton className="h-32" />;
  if (metrics.isError) return <ErrorState error={metrics.error} onRetry={() => metrics.refetch()} />;
  if (!metrics.data.length) return <EmptyState icon={Sparkles} title="Sin datos aún" description="Las métricas aparecen cuando los estudiantes reciben y responden recomendaciones." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">Tipo</th><th className="py-2 pr-3 font-medium">Generadas</th>
            <th className="py-2 pr-3 font-medium">Completadas</th><th className="py-2 pr-3 font-medium">Descartadas</th>
            <th className="py-2 pr-3 font-medium">Aceptación</th><th className="py-2 font-medium">Utilidad declarada</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {metrics.data.map((m) => (
            <tr key={m.kind}>
              <td className="py-2 pr-3">{KIND_META[m.kind]?.label ?? m.kind}</td>
              <td className="py-2 pr-3">{m.total}</td><td className="py-2 pr-3">{m.completada}</td>
              <td className="py-2 pr-3">{m.descartada}</td><td className="py-2 pr-3">{pct(m.acceptance_rate)}</td>
              <td className="py-2">{pct(m.useful_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-muted">Aceptación = (aceptadas + completadas) / decididas. Se mide la utilidad declarada, no solo clics (§4.11).</p>
    </div>
  );
}

/** Docente y gestión (D55): qué conviene hacer hoy con los grupos a cargo, calculado con datos reales. */
function TeacherActions() {
  const actions = useQuery({ queryKey: ["recommendations", "teacher-actions"], queryFn: () => api<TeacherAction[]>("/recommendations/teacher-actions") });
  if (actions.isPending) return <Skeleton className="h-48" />;
  if (actions.isError) return <ErrorState error={actions.error} onRetry={() => actions.refetch()} />;
  if (!actions.data.length) return <EmptyState icon={Sparkles} title="Nada urgente" description="No hay entregas por calificar, alertas pendientes ni estudiantes inactivos en tus grupos." />;
  return (
    <ul className="flex flex-col gap-3">
      {actions.data.map((a, i) => {
        const meta = ACTION_META[a.kind];
        return (
          <li key={i} className="panel flex flex-wrap items-start gap-3 p-4">
            <meta.icon className="mt-0.5 size-5 shrink-0 text-cyan" aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{a.title}</p><Badge tone={meta.tone}>{a.course}</Badge></div>
              <p className="mt-0.5 text-sm text-muted">{a.reason}</p>
            </div>
            <Link to={a.link} className="inline-flex items-center gap-1 rounded-[10px] bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1a8cf0]">
              {meta.cta} <ArrowRight className="size-3.5" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Lo que el motor sugiere a cada estudiante de un grupo (§4.5: el docente revisa; su criterio prevalece). */
function GroupSuggestions() {
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const [offeringId, setOfferingId] = useState("");
  const recs = useQuery({
    queryKey: ["recommendations", "offering", offeringId],
    queryFn: () => api<Recommendation[]>(`/offerings/${offeringId}/recommendations`),
    enabled: !!offeringId,
  });
  const open = recs.data?.filter((r) => r.status === "nueva" || r.status === "aceptada") ?? [];
  return (
    <Panel title="Sugerencias a tus estudiantes" subtitle="Lo que el motor recomienda a cada uno, con su motivo">
      <label className="sr-only" htmlFor="rec-offering">Oferta</label>
      <select id="rec-offering" className="field mb-3 max-w-md" value={offeringId} onChange={(e) => setOfferingId(e.target.value)}>
        <option value="">Elige una oferta…</option>
        {offerings.data?.filter((o) => o.can_manage).map((o) => <option key={o.id} value={o.id}>{o.course_code} · {o.course_title} ({o.cohort})</option>)}
      </select>
      {!offeringId ? <p className="text-sm text-muted">Elige una oferta para ver las sugerencias vigentes de su grupo.</p>
        : recs.isPending ? <Skeleton className="h-32" />
        : recs.isError ? <ErrorState error={recs.error} />
        : open.length === 0 ? <p className="text-sm text-muted">No hay sugerencias vigentes en este grupo.</p> : (
          <ul className="divide-y divide-line">
            {open.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-3 py-2.5 text-sm">
                <Badge tone={KIND_META[r.kind]?.tone ?? "muted"}>{KIND_META[r.kind]?.label ?? r.kind}</Badge>
                <div className="min-w-0 flex-1">
                  <p><span className="font-medium">{r.student_name}</span> · {r.title}</p>
                  <p className="text-xs text-muted">{r.reason}</p>
                </div>
                <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
              </li>
            ))}
          </ul>
        )}
    </Panel>
  );
}

/** Gestión (D55): aceptación por semana y por curso, y motivos de descarte para ajustar las reglas. */
function ManagementInsights() {
  const data = useQuery({ queryKey: ["recommendations", "insights"], queryFn: () => api<Insights>("/recommendations/insights") });
  const fmtWeek = new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short" });
  return (
    <div className="flex flex-col gap-4">
      <Panel title="Aceptación y utilidad por tipo" subtitle="Agregado de tu institución"><MetricsTable /></Panel>
      {data.isPending && <Skeleton className="h-48" />}
      {data.isError && <ErrorState error={data.error} onRetry={() => data.refetch()} />}
      {data.data && (
        <>
          <Panel title="Evolución semanal" subtitle="Sugerencias generadas y qué hicieron los estudiantes con ellas">
            {data.data.weekly.length >= 2 ? (
              <TrendChart labels={data.data.weekly.map((w) => fmtWeek.format(new Date(w.week_start)))} series={[
                { key: "g", label: "Generadas", unit: "sug.", color: "#20c8f5", values: data.data.weekly.map((w) => w.generated) },
                { key: "c", label: "Completadas", unit: "sug.", color: "#00bfa6", values: data.data.weekly.map((w) => w.completed) },
                { key: "a", label: "Aceptadas", unit: "sug.", color: "#8b4dff", values: data.data.weekly.map((w) => w.accepted) },
                { key: "d", label: "Descartadas", unit: "sug.", color: "#ff5c8a", values: data.data.weekly.map((w) => w.discarded) },
              ]} />
            ) : data.data.weekly.length === 1 ? (
              // Con una sola semana no hay tendencia que dibujar: se muestran sus cifras.
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {([["Generadas", "generated"], ["Completadas", "completed"], ["Aceptadas", "accepted"], ["Descartadas", "discarded"]] as const).map(([k, f]) => (
                  <div key={k}><dt className="text-xs text-muted">{k} · semana del {fmtWeek.format(new Date(data.data.weekly[0]!.week_start))}</dt>
                    <dd className="text-xl font-semibold">{data.data.weekly[0]![f]}</dd></div>
                ))}
              </dl>
            ) : <p className="text-sm text-muted">Aún no hay sugerencias registradas.</p>}
          </Panel>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Por curso" subtitle="Dónde sirven más las sugerencias">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-muted"><tr className="border-b border-line">
                  <th className="py-2 pr-3 font-medium">Curso</th><th className="py-2 pr-3 font-medium">Generadas</th>
                  <th className="py-2 pr-3 font-medium">Aceptación</th><th className="py-2 font-medium">Utilidad</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {data.data.by_course.map((c) => (
                    <tr key={c.course}><td className="py-2 pr-3">{c.course}</td><td className="py-2 pr-3">{c.total}</td>
                      <td className="py-2 pr-3">{pct(c.acceptance_rate)}</td><td className="py-2">{pct(c.useful_rate)}</td></tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <Panel title="Motivos de descarte más frecuentes" subtitle="Lo que escribieron los estudiantes al descartar">
              {data.data.discard_reasons.length ? (
                <ul className="divide-y divide-line text-sm">
                  {data.data.discard_reasons.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-3 py-2"><span>{r.reason}</span><Badge tone="muted">{r.count}</Badge></li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted">Nadie ha descartado sugerencias todavía.</p>}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

/** Estudiante: cómo le han servido sus sugerencias, con su propio historial. */
function MyUsefulness({ rows }: { rows: Recommendation[] }) {
  const count = (f: (r: Recommendation) => boolean) => rows.filter(f).length;
  const rated = count((r) => r.useful !== null);
  const kinds = [...new Set(rows.map((r) => r.kind))];
  if (!rows.length) return <EmptyState icon={Sparkles} title="Sin historial aún" description="Cuando sigas o descartes sugerencias, aquí verás cómo te han servido." />;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[["Recibidas", rows.length], ["Las hiciste", count((r) => r.status === "completada")],
          ["Descartadas", count((r) => r.status === "descartada")], ["Te sirvieron", rated ? `${count((r) => r.useful === true)} de ${rated}` : "—"]]
          .map(([k, v]) => <div key={k} className="panel p-3"><p className="text-[11px] text-muted">{k}</p><p className="text-xl font-semibold">{v}</p></div>)}
      </div>
      <Panel title="Por tipo de sugerencia">
        <ul className="divide-y divide-line text-sm">
          {kinds.map((k) => {
            const of = rows.filter((r) => r.kind === k);
            return (
              <li key={k} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Badge tone={KIND_META[k]?.tone ?? "muted"}>{KIND_META[k]?.label ?? k}</Badge>
                <span className="text-muted">{of.length} recibidas · {of.filter((r) => r.status === "completada").length} hechas · {of.filter((r) => r.useful === true).length} útiles</span>
              </li>
            );
          })}
        </ul>
      </Panel>
      <p className="text-[11px] text-muted">Marcar «útil» o «no útil» ayuda a mejorar el motor: esas respuestas entrenarán el ranking aprendido (cabeza D de §9.1).</p>
    </div>
  );
}

export function RecommendationsPage() {
  const { can } = useAuth();
  const student = can("learning") && !can("course.read.all");
  const current = useMyRecommendations(undefined, false, student);
  const history = useMyRecommendations(undefined, true, student);

  if (!student) {
    const items: TabItem[] = [];
    if (can("assessment.manage")) {
      items.push({ id: "acciones", label: "Acciones sugeridas", content: <TeacherActions /> });
      items.push({ id: "grupos", label: "Sugerencias de mis grupos", content: <GroupSuggestions /> });
    }
    if (can("ml.read") || can("course.read.all")) items.push({ id: "metricas", label: "Métricas", content: <ManagementInsights /> });
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <PageHeader title="Recomendaciones" description="Motor de reglas explicable (D27, D55): qué conviene hacer hoy, qué se sugiere a cada estudiante y cuánto sirve." />
        {items.length ? <Tabs label="Secciones de recomendaciones" param="seccion" items={items} />
          : <Panel><p className="text-sm text-muted">Tu rol no tiene recomendaciones que revisar.</p></Panel>}
      </div>
    );
  }

  const closed = history.data?.filter((r) => r.status !== "nueva" && r.status !== "aceptada") ?? [];
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <PageHeader title="Mis recomendaciones" description="Todas tus sugerencias, por qué van en ese orden y cómo te han servido. Para la pregunta rápida, usa el IA Tutor."
        actions={<Link to="/tutor" className="inline-flex items-center gap-2 rounded-[10px] border border-line bg-surface-2/40 px-3.5 py-2 text-sm font-medium hover:border-cyan/60 hover:text-cyan"><Bot className="size-4" aria-hidden /> IA Tutor</Link>} />
      <Tabs label="Mis recomendaciones" param="seccion" items={[
        { id: "vigentes", label: "Vigentes", badge: current.data ? <Badge tone="cyan">{current.data.length}</Badge> : undefined, content: (
          <>
            {current.isPending && <Skeleton className="h-64" />}
            {current.isError && <ErrorState error={current.error} onRetry={() => current.refetch()} />}
            {current.data?.length === 0 && <EmptyState icon={Sparkles} title="¡Todo al día!" description="No hay sugerencias pendientes en tus cursos." />}
            <div className="flex flex-col gap-3">{current.data?.map((r) => <RecommendationCard key={r.id} r={r} />)}</div>
            <p className="text-[11px] text-muted">Ordenadas por prioridad: cada tarjeta dice por qué va en su lugar. Son orientativas; tu docente puede verlas y su criterio prevalece (§4.5).</p>
          </>
        ) },
        { id: "historial", label: "Historial", content: history.isPending ? <Skeleton className="h-64" /> : (
          closed.length ? <div className="flex flex-col gap-3">{closed.map((r) => <RecommendationCard key={r.id} r={r} />)}</div>
            : <EmptyState icon={Sparkles} title="Sin historial aún" description="Aquí aparecen las sugerencias que hiciste, descartaste o que dejaron de aplicar, con el motivo." />
        ) },
        { id: "utilidad", label: "Cómo me han servido", content: <MyUsefulness rows={history.data ?? []} /> },
      ]} />
    </div>
  );
}

export function TutorPage() {
  const { can, user } = useAuth();
  const student = can("learning") && !can("course.read.all");
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings"), enabled: student });
  const [offeringId, setOfferingId] = useState<string>("");
  const [asked, setAsked] = useState(false);
  const recs = useMyRecommendations(offeringId || undefined, false, student);

  if (!student) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title="IA Tutor" description="Asistente del estudiante (§4.5)." />
        <EmptyState icon={Bot} title="Disponible para estudiantes" description="Cada estudiante pregunta «¿qué hago ahora?» en un curso y recibe sugerencias explicadas. El docente las ve en el detalle del curso." />
      </div>
    );
  }
  const active = offerings.data?.filter((o) => o.my_enrollment?.status === "active") ?? [];

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="IA Tutor" description="Elige un curso y pregunta qué hacer ahora. El tutor revisa tu avance, entregas y notas." />
      <Panel glow>
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet"><Bot className="size-5" /></div>
          <div className="flex-1">
            <p className="text-sm">Hola, {user?.full_name.split(" ")[0]}. ¿En qué curso quieres avanzar?</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <select className="field max-w-sm" aria-label="Curso" value={offeringId} onChange={(e) => { setOfferingId(e.target.value); setAsked(false); }}>
                <option value="">Todos mis cursos</option>
                {active.map((o) => <option key={o.id} value={o.id}>{o.course_title}</option>)}
              </select>
              <Button icon={Sparkles} onClick={() => { setAsked(true); recs.refetch(); }}>¿Qué hago ahora?</Button>
            </div>
          </div>
        </div>
      </Panel>
      {asked && (
        <div className="mt-4 flex flex-col gap-3">
          {recs.isFetching && <Skeleton className="h-32" />}
          {recs.isError && <ErrorState error={recs.error} />}
          {recs.data && !recs.isFetching && (recs.data.length === 0 ? (
            <EmptyState icon={Sparkles} title="Vas al día" description="No encontré nada pendiente. ¡Sigue así!" />
          ) : (
            <>
              <p className="text-sm text-muted">Te sugiero esto, en orden de prioridad:</p>
              {/* Solo por prioridad (no por estado): al aceptar, la tarjeta queda en su sitio como «aceptada»
                  en vez de bajar y salir de las 3 visibles. */}
              {[...recs.data].sort((a, b) => b.priority - a.priority).slice(0, 3)
                .map((r) => <RecommendationCard key={r.id} r={r} />)}
              <p className="text-[11px] text-muted">Motor <Badge tone="muted">{recs.data[0]?.source}</Badge> · orientativo, no reemplaza a tu docente.</p>
            </>
          ))}
        </div>
      )}
    </div>
  );
}
