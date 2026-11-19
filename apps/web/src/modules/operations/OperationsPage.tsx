import { useQuery } from "@tanstack/react-query";
import { Badge, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";

interface RouteStat { route: string; requests: number; errors_5xx: number; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null }
interface OpsMetrics {
  uptime_seconds: number;
  requests_total: number;
  status: Record<string, number>;
  error_rate_5xx: number;
  throughput_rpm: number;
  latency_ms: { p50: number | null; p95: number | null; p99: number | null };
  routes: RouteStat[];
  targets: { api_read_p95_ms: number; dashboard_p95_ms: number; inference_p95_ms: number; error_rate_5xx: number };
  realtime: { sse_connections: number; users_online: number };
  freshness: { last_learning_event_at: string | null };
  predictions_7d: Record<string, number>;
  environment: string;
}

function uptime(s: number) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}

function Stat({ label, value, hint, ok }: { label: string; value: string; hint?: string; ok?: boolean }) {
  return (
    <div className="rounded-xl border border-line bg-bg/40 p-3">
      <p className="text-[11px] text-muted">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-xl font-semibold">
        {value}
        {ok !== undefined && <Badge tone={ok ? "teal" : "warning"}>{ok ? "dentro del objetivo" : "fuera del objetivo"}</Badge>}
      </p>
      {hint && <p className="mt-0.5 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

/** Operación (§12.1, D41): métricas reales del proceso de la API comparadas con los objetivos de §10.5. */
export function OperationsPage() {
  const q = useQuery({ queryKey: ["ops"], queryFn: () => api<OpsMetrics>("/system/metrics"), refetchInterval: 10_000 });
  if (q.isPending) return <Skeleton className="h-96" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const m = q.data;
  const p95 = m.latency_ms.p95;
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Operación"
        description="Métricas en vivo de la API desde su último arranque (se actualizan cada 10 s). No contienen datos personales." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Latencia p95 (todas las rutas)" value={p95 !== null ? `${p95} ms` : "—"}
          hint={`objetivo lectura común: ${m.targets.api_read_p95_ms} ms`} ok={p95 !== null ? p95 <= m.targets.api_read_p95_ms : undefined} />
        <Stat label="Errores 5xx (últimos 5 min)" value={`${(m.error_rate_5xx * 100).toFixed(2)} %`}
          hint={`objetivo: < ${m.targets.error_rate_5xx * 100} %`} ok={m.error_rate_5xx < m.targets.error_rate_5xx} />
        <Stat label="Throughput" value={`${m.throughput_rpm} pet/min`} hint={`${m.requests_total} peticiones en total`} />
        <Stat label="Tiempo en marcha" value={uptime(m.uptime_seconds)} hint={`ambiente: ${m.environment}`} />
        <Stat label="Conexiones en vivo (SSE)" value={String(m.realtime.sse_connections)} hint={`${m.realtime.users_online} personas conectadas`} />
        <Stat label="Último evento de aprendizaje" value={m.freshness.last_learning_event_at ? formatDateTime(m.freshness.last_learning_event_at) : "—"}
          hint="frescura de los datos del panel" />
        <Stat label="Predicciones (7 días)" value={String(Object.values(m.predictions_7d).reduce((a, b) => a + b, 0))}
          hint={Object.entries(m.predictions_7d).map(([k, v]) => `${k}: ${v}`).join(" · ") || "sin inferencias recientes"} />
        <Stat label="Respuestas por código" value={Object.entries(m.status).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"} />
      </div>
      <Panel title="Latencia por ruta" subtitle="Plantilla de ruta (sin identificadores), últimas 2 000 peticiones por ruta, ordenadas por p95">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted">
              <tr><th className="py-2 pr-3 font-medium">Ruta</th><th className="pr-3 font-medium">Peticiones</th>
                <th className="pr-3 font-medium">5xx</th><th className="pr-3 font-medium">p50</th>
                <th className="pr-3 font-medium">p95</th><th className="font-medium">p99</th></tr>
            </thead>
            <tbody>
              {m.routes.map((r) => (
                <tr key={r.route} className="border-t border-line/60">
                  <td className="py-1.5 pr-3 font-mono text-[11px]">{r.route}</td>
                  <td className="pr-3">{r.requests}</td>
                  <td className={r.errors_5xx ? "pr-3 text-danger" : "pr-3"}>{r.errors_5xx}</td>
                  <td className="pr-3">{r.p50_ms ?? "—"} ms</td>
                  <td className={(r.p95_ms ?? 0) > m.targets.api_read_p95_ms ? "pr-3 text-warning" : "pr-3"}>{r.p95_ms ?? "—"} ms</td>
                  <td>{r.p99_ms ?? "—"} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
