import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Circle,
  CircleDot,
  Grid3x3,
  LineChart,
  Map,
  PieChart,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router";
import { PHASES } from "../../app/modules";
import { Donut, TrendChart } from "../../components/charts";
import { PeruTileMap, type RegionValue } from "../../components/charts/PeruTileMap";
import { HeatmapTable, LevelDots } from "../skills/SkillsPage";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { actorLabel, formatNumber, formatTime, relativeTime, variation } from "../../lib/format";
import { Badge, EmptyState, ErrorState, Panel, Skeleton, cx } from "../../components/ui";
import { ACTION_TONE, useActivity } from "../audit/activity";
import { NeuralNetwork, useArchitecture } from "../neural-visualizer/NeuralNetwork";
import { RecommendationCard } from "../recommendations/RecommendationCard";
import { MetricsTable, useMyRecommendations } from "../recommendations/RecommendationsPage";

interface Kpi {
  key: string;
  label: string;
  value: number;
  previous: number | null;
  unit: string;
  source: string;
  updated_at: string;
}

interface Summary {
  scope: string;
  generated_at: string;
  kpis: Kpi[];
}

function KpiCard({ kpi }: { kpi: Kpi }) {
  const delta = variation(kpi.value, kpi.previous);
  return (
    <div className="panel flex flex-col gap-1 p-4">
      <p className="text-xs text-muted">{kpi.label}</p>
      <div className="flex items-end gap-2">
        <p className="text-2xl font-semibold tracking-tight">
          {formatNumber(kpi.value)}{kpi.unit === "%" && <span className="text-base text-muted"> %</span>}
        </p>
        {delta !== null && (
          <span className={cx("mb-1 inline-flex items-center text-xs font-medium", delta >= 0 ? "text-teal" : "text-danger")}>
            {delta >= 0 ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
            {Math.abs(delta)}%
          </span>
        )}
      </div>
      <p className="text-[10.5px] text-muted/80" title={`Fuente: ${kpi.source}`}>
        {kpi.previous !== null ? `vs. ${formatNumber(kpi.previous)} periodo anterior · ` : ""}
        {kpi.source} · {formatTime(kpi.updated_at)}
      </p>
    </div>
  );
}

function KpiGrid() {
  const summary = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api<Summary>("/dashboard/summary"),
    refetchInterval: 60_000,
  });
  if (summary.isPending)
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
      </div>
    );
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {summary.data.kpis.map((k) => <KpiCard key={k.key} kpi={k} />)}
      <div className="col-span-full rounded-xl border border-dashed border-line p-3 text-[11px] text-muted">
        Calculado desde eventos y matrículas reales de la base (datos de instituciones DEMO).
        Alcance: <span className="text-text">{summary.data.scope}</span>.
      </div>
    </div>
  );
}

interface WeekPoint { week_start: string; active_students: number; activities_completed: number; hours: number }
interface Completion { completed: number; in_progress: number; not_started: number; total: number }

function ProgressPanel() {
  const series = useQuery({ queryKey: ["dashboard", "series"], queryFn: () => api<WeekPoint[]>("/dashboard/progress-series?weeks=8") });
  const fmt = new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short" });
  return (
    <Panel title="Progreso de aprendizaje" subtitle="Últimas 8 semanas · desde learning_events">
      {series.isPending && <Skeleton className="h-52" />}
      {series.isError && <ErrorState error={series.error} onRetry={() => series.refetch()} />}
      {series.data && (series.data.every((p) => p.active_students === 0) ? (
        <EmptyState icon={LineChart} title="Sin actividad registrada" description="Aún no hay eventos de aprendizaje en tus cursos." />
      ) : (
        <TrendChart labels={series.data.map((p) => fmt.format(new Date(p.week_start)))} series={[
          { key: "act", label: "Actividades completadas", unit: "act.", color: "#20c8f5", values: series.data.map((p) => p.activities_completed) },
          { key: "stu", label: "Estudiantes activos", unit: "est.", color: "#8b4dff", values: series.data.map((p) => p.active_students) },
          { key: "hrs", label: "Horas", unit: "h", color: "#00bfa6", values: series.data.map((p) => p.hours) },
        ]} />
      ))}
    </Panel>
  );
}

function CompletionPanel() {
  const data = useQuery({ queryKey: ["dashboard", "completion"], queryFn: () => api<Completion>("/dashboard/completion") });
  return (
    <Panel title="Finalización de cursos" subtitle="Estado de las matrículas vigentes">
      {data.isPending && <Skeleton className="h-36" />}
      {data.isError && <ErrorState error={data.error} onRetry={() => data.refetch()} />}
      {data.data && (data.data.total === 0 ? (
        <EmptyState icon={PieChart} title="Sin matrículas" description="Todavía no hay matrículas en tus cursos." />
      ) : (
        <Donut center={`${Math.round((100 * data.data.completed) / data.data.total)} %`} slices={[
          { label: "Completado", value: data.data.completed, color: "#00bfa6" },
          { label: "En progreso", value: data.data.in_progress, color: "#087fe5" },
          { label: "No iniciado", value: data.data.not_started, color: "#8b4dff" },
        ]} />
      ))}
    </Panel>
  );
}

interface Geo { k: number; regions: RegionValue[]; suppressed_students: number; without_region: number }

function SkillsPanel() {
  const { can } = useAuth();
  const staff = can("analytics.read");
  const heat = useQuery({ queryKey: ["skills", "heatmap", ""], enabled: staff,
    queryFn: () => api<{ levels: string[]; engine: string; students: number; rows: { skill_id: string; code: string; name: string; estimated: number[]; validated: number[] }[] }>("/analytics/skill-mastery") });
  const mine = useQuery({ queryKey: ["skills", "mine"], enabled: !staff,
    queryFn: () => api<{ skill_id: string; name: string; estimated_level: number | null; validated_level: number | null }[]>("/my/skills") });
  return (
    <Panel title="Dominio de habilidades" subtitle={staff ? "Estudiantes por competencia y nivel estimado" : "Tu nivel estimado y validado"}
      actions={<Link to="/habilidades" className="text-xs text-cyan hover:underline">Ver detalle</Link>}>
      {(heat.isPending && staff) || (mine.isPending && !staff) ? <Skeleton className="h-40" /> : null}
      {staff && heat.data && (heat.data.rows.length ? <HeatmapTable data={heat.data} mode="estimated" /> :
        <EmptyState icon={Grid3x3} title="Sin competencias vinculadas" description="Vincula competencias a los cursos." />)}
      {!staff && mine.data && (mine.data.length === 0 ? <EmptyState icon={Grid3x3} title="Sin evidencias aún" description="Avanza en tus cursos." /> : (
        <ul className="space-y-1.5 text-sm">
          {mine.data.slice(0, 6).map((s) => (
            <li key={s.skill_id} className="flex items-center justify-between gap-2"><span className="truncate">{s.name}</span><LevelDots level={s.validated_level ?? s.estimated_level} validated={!!s.validated_level} /></li>
          ))}
        </ul>
      ))}
    </Panel>
  );
}

function MapPanel() {
  const { can } = useAuth();
  const staff = can("course.read.all") || can("assessment.manage");
  const geo = useQuery({ queryKey: ["dashboard", "geo"], queryFn: () => api<Geo>("/dashboard/geo"), enabled: staff });
  return (
    <Panel title="Mapa de progreso" subtitle="Progreso promedio por región · solo agregados">
      {!staff && <EmptyState icon={Map} title="Vista institucional" description="El mapa agregado está disponible para docentes y coordinación." />}
      {staff && geo.isPending && <Skeleton className="h-52" />}
      {staff && geo.isError && <ErrorState error={geo.error} onRetry={() => geo.refetch()} />}
      {geo.data && (
        <>
          <PeruTileMap data={geo.data.regions} />
          <p className="mt-3 text-[11px] text-muted">
            Regiones con menos de {geo.data.k} estudiantes no se muestran ni se nombran
            ({geo.data.suppressed_students} ocultos){geo.data.without_region ? ` · ${geo.data.without_region} sin región` : ""}.
          </p>
        </>
      )}
    </Panel>
  );
}

function RecommendationsPanel() {
  const { can } = useAuth();
  const student = can("learning") && !can("course.read.all");
  const recs = useMyRecommendations(undefined, false, student);
  return (
    <Panel title="Recomendaciones de IA" subtitle={student ? "Tus próximos pasos, con su motivo" : "Aceptación y utilidad (§4.11)"}
      actions={<Link to="/recomendaciones" className="text-xs text-cyan hover:underline">Ver todo</Link>}>
      {student ? (
        <>
          {recs.isPending && <Skeleton className="h-36" />}
          {recs.isError && <ErrorState error={recs.error} onRetry={() => recs.refetch()} />}
          {recs.data?.length === 0 && <EmptyState icon={Sparkles} title="Todo al día" description="No hay sugerencias pendientes." />}
          <div className="flex flex-col gap-3">{recs.data?.slice(0, 2).map((r) => <RecommendationCard key={r.id} r={r} compact />)}</div>
        </>
      ) : can("ml.read") || can("course.read.all") ? <MetricsTable /> : (
        <p className="text-sm text-muted">Las sugerencias de tu grupo están en el detalle de cada curso.</p>
      )}
    </Panel>
  );
}

const HEADLINE = {
  staff: ["students", "courses", "learning_hours_30d", "certificates"],
  student: ["my_courses", "my_progress", "my_hours_7d", "my_logins_24h"],
};

function HeadlineKpis() {
  const summary = useQuery({ queryKey: ["dashboard", "summary"], queryFn: () => api<Summary>("/dashboard/summary"), refetchInterval: 60_000 });
  if (!summary.data) return <Skeleton className="h-20" />;
  const keys = summary.data.scope === "personal" ? HEADLINE.student : HEADLINE.staff;
  const kpis = keys.map((k) => summary.data.kpis.find((x) => x.key === k)).filter((k): k is Kpi => !!k);
  return <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{kpis.map((k) => <KpiCard key={k.key} kpi={k} />)}</div>;
}

function NeuralPanel() {
  const arch = useArchitecture();
  return (
    <Panel glow title="Arquitectura de aprendizaje inteligente"
      subtitle="Red multitarea de §9.1: entrada → embeddings → GRU → fusión → 4 salidas"
      actions={<Link to="/red-neuronal" className="text-xs text-cyan hover:underline">Ver detalle</Link>}>
      {arch.isPending && <Skeleton className="h-64" />}
      {arch.isError && <ErrorState error={arch.error} onRetry={() => arch.refetch()} />}
      {arch.data && (
        <div className="flex flex-col gap-4">
          <NeuralNetwork arch={arch.data} compact labeled />
          <HeadlineKpis />
        </div>
      )}
    </Panel>
  );
}

function ActivityPanel() {
  const activity = useActivity("", 8);
  const items = activity.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <Panel title="Actividad reciente" subtitle="Bitácora de auditoría filtrada por tus permisos"
      actions={<Link to="/actividad" className="text-xs text-cyan hover:underline">Ver todo</Link>}>
      {activity.isPending && <Skeleton className="h-40" />}
      {activity.isError && <ErrorState error={activity.error} onRetry={() => activity.refetch()} />}
      {activity.isSuccess && items.length === 0 && (
        <EmptyState icon={CircleDot} title="Sin actividad" description="Aún no hay acciones registradas visibles para ti." />
      )}
      <ul className="divide-y divide-line">
        {items.map((a) => (
          <li key={a.id} className="flex items-center gap-3 py-2.5 text-sm">
            <span className={cx("size-2 shrink-0 rounded-full",
              ACTION_TONE[a.action] === "danger" ? "bg-danger" : ACTION_TONE[a.action] === "teal" ? "bg-teal" : "bg-cyan")} />
            <p className="min-w-0 flex-1 truncate">
              <span className="font-medium">{actorLabel(a.actor_name, a.action)}</span>{" "}
              <span className="text-muted">· {a.label}</span>
            </p>
            <time className="shrink-0 text-xs text-muted" dateTime={a.occurred_at}>{relativeTime(a.occurred_at)}</time>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function RoadmapPanel() {
  return (
    <Panel title="Hoja de ruta" subtitle="Fases de §14 · avance real del proyecto">
      <ol className="space-y-2">
        {PHASES.map((p) => (
          <li key={p.n} className="flex items-start gap-2.5 text-sm">
            {p.status === "done" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-teal" />
              : p.status === "partial" ? <CircleDot className="mt-0.5 size-4 shrink-0 text-cyan" />
              : <Circle className="mt-0.5 size-4 shrink-0 text-muted/50" />}
            <span className={cx(p.status === "partial" ? "text-cyan" : p.status === "done" ? "text-text" : "text-muted")}>
              {p.n}. {p.name}
              {p.note && <span className="block text-[11px] text-muted">{p.note}</span>}
            </span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Hola, {user?.full_name.split(" ")[0]}</h1>
          <p className="text-sm text-muted">Resumen de {user?.organization.name}</p>
        </div>
        <Badge tone="warning">Datos de instituciones DEMO</Badge>
      </div>

      {/* Composición de la referencia: red + indicadores | progreso; mapa · finalización · habilidades;
          recomendaciones · actividad · hoja de ruta; indicadores detallados al final. */}
      <div className="grid gap-4 xl:grid-cols-2">
        <NeuralPanel />
        <ProgressPanel />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <MapPanel />
        <CompletionPanel />
        <SkillsPanel />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <RecommendationsPanel />
        <ActivityPanel />
        <RoadmapPanel />
      </div>
      <Panel title="Indicadores detallados" subtitle="Valor, variación, fuente y hora de cálculo de cada KPI">
        <KpiGrid />
      </Panel>
    </div>
  );
}
