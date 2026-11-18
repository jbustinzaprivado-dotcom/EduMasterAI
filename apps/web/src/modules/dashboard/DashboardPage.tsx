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
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatNumber, formatTime, relativeTime, variation } from "../../lib/format";
import { Badge, EmptyState, ErrorState, Panel, Skeleton, cx } from "../../components/ui";
import { ACTION_TONE, useActivity } from "../audit/activity";
import { ModelStatus, NeuralNetwork, useArchitecture } from "../neural-visualizer/NeuralNetwork";
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
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-2">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
      </div>
    );
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-2">
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
    <Panel className="lg:col-span-2" title="Progreso de aprendizaje" subtitle="Últimas 8 semanas · desde learning_events">
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

function RecommendationsPanel() {
  const { can } = useAuth();
  const student = can("learning") && !can("course.read.all");
  const recs = useMyRecommendations(undefined, false);
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

function NeuralPanel() {
  const arch = useArchitecture();
  return (
    <Panel glow className="xl:col-span-2" title="Arquitectura de aprendizaje inteligente"
      subtitle="Red multitarea de §9.1: entrada → embeddings → GRU → fusión → 4 salidas"
      actions={<Link to="/red-neuronal" className="text-xs text-cyan hover:underline">Ver detalle</Link>}>
      {arch.isPending && <Skeleton className="h-64" />}
      {arch.isError && <ErrorState error={arch.error} onRetry={() => arch.refetch()} />}
      {arch.data && (
        <div className="grid gap-4 2xl:grid-cols-[1fr_220px]">
          <NeuralNetwork arch={arch.data} compact />
          <div className="rounded-xl border border-line bg-bg/40 p-3">
            <p className="mb-2 text-xs font-semibold">Estado del modelo</p>
            <ModelStatus arch={arch.data} />
          </div>
        </div>
      )}
    </Panel>
  );
}

function ActivityPanel() {
  const activity = useActivity("", 8);
  const items = activity.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <Panel className="lg:col-span-2" title="Actividad reciente" subtitle="Bitácora de auditoría filtrada por tus permisos"
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
              <span className="font-medium">{a.actor_name ?? "Usuario no identificado"}</span>{" "}
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

      {/* Fila 1: arquitectura neuronal + KPIs (§5.2) */}
      <div className="grid gap-4 xl:grid-cols-3">
        <NeuralPanel />
        <Panel title="Indicadores" subtitle="Valor, variación, fuente y hora de cálculo">
          <KpiGrid />
        </Panel>
      </div>

      {/* Fila 2: tendencias y mapa */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ProgressPanel />
        <Panel title="Mapa de progreso" subtitle="Distribución geográfica agregada">
          <EmptyState icon={Map} phase={3} title="Agregado por región"
            description="Solo datos geográficos permitidos y agregados; nunca ubicaciones individuales." />
        </Panel>
      </div>

      {/* Fila 3: finalización, habilidades, recomendaciones */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <CompletionPanel />
        <Panel title="Dominio de habilidades" subtitle="Heatmap por competencia y nivel">
          <EmptyState icon={Grid3x3} phase={4} title="Evidencias de evaluación"
            description="El nivel estimado por IA se mostrará separado del validado por el docente." />
        </Panel>
        <RecommendationsPanel />
      </div>

      {/* Fila 4: actividad + hoja de ruta */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ActivityPanel />
        <RoadmapPanel />
      </div>
    </div>
  );
}
