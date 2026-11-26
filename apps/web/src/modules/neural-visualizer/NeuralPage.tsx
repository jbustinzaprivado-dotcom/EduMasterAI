import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { PageHeader, Panel, ErrorState, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Offering, RosterRow } from "../courses/api";
import { ModelStatus, NeuralNetwork, useArchitecture } from "./NeuralNetwork";
import { TraceView } from "./TraceView";

const STATES = [
  ["Detenido", "Sin proceso activo."],
  ["Cargando datos", "Lectura del dataset versionado."],
  ["Entrenando", "Retropropagación real (pulsos de derecha a izquierda)."],
  ["Validando", "Métricas sobre el conjunto de validación temporal."],
  ["Publicado", "Versión aprobada en el registro de modelos."],
  ["Inferencia activa", "Propagación hacia delante con datos reales."],
  ["Error", "Fallo del proceso con su correlation_id."],
];

/** Recorrido real (D51): solo para quien ve el riesgo nominal (docente, administración, auditoría; nunca el estudiante). */
function TracePanel() {
  const [params, setParams] = useSearchParams();
  const enrollmentId = params.get("matricula");
  const offeringId = params.get("oferta");
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const roster = useQuery({
    queryKey: ["roster", offeringId],
    queryFn: () => api<RosterRow[]>(`/offerings/${offeringId}/enrollments`),
    enabled: !!offeringId,
  });
  const set = (next: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    setParams(p, { replace: true });
  };

  return (
    <Panel title="Recorrido real de una predicción"
      subtitle="Elige un estudiante: la red se recorre con sus datos actuales y muestra las neuronas que más aportaron.">
      <div className="mb-3 flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="trace-offering">Oferta</label>
        <select id="trace-offering" className="field w-auto text-sm" value={offeringId ?? ""}
          onChange={(e) => set({ oferta: e.target.value || null, matricula: null })}>
          <option value="">Elige una oferta…</option>
          {(offerings.data ?? []).filter((o) => o.status === "active").map((o) => (
            <option key={o.id} value={o.id}>{o.course_code} · {o.course_title} ({o.cohort})</option>
          ))}
        </select>
        <label className="sr-only" htmlFor="trace-student">Estudiante</label>
        <select id="trace-student" className="field w-auto text-sm" value={enrollmentId ?? ""} disabled={!offeringId}
          onChange={(e) => set({ matricula: e.target.value || null })}>
          <option value="">Elige un estudiante…</option>
          {(roster.data ?? []).filter((r) => r.status === "active").map((r) => (
            <option key={r.enrollment_id} value={r.enrollment_id}>{r.student_name}</option>
          ))}
        </select>
      </div>
      {enrollmentId
        ? <TraceView enrollmentId={enrollmentId} />
        : <p className="text-xs text-muted">Aún no elegiste un estudiante. También puedes abrirlo desde la alerta de riesgo en la ficha del curso.</p>}
    </Panel>
  );
}

export function NeuralPage() {
  const arch = useArchitecture();
  const { can } = useAuth();
  const canTrace = can("assessment.manage") || can("audit.read");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Arquitectura neuronal" description="Visualizador de §4.10: topología y estado del modelo publicado en tu institución." />
      {arch.isPending && <Skeleton className="h-96" />}
      {arch.isError && <ErrorState error={arch.error} onRetry={() => arch.refetch()} />}
      {arch.data && (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          <Panel glow title={arch.data.model_name} subtitle={arch.data.note}>
            <NeuralNetwork arch={arch.data} />
          </Panel>
          <div className="flex flex-col gap-4">
            <Panel title="Estado del modelo"><ModelStatus arch={arch.data} /></Panel>
            <Panel title="Estados que distinguirá la interfaz" subtitle="Principio de transparencia (§1)">
              <ul className="space-y-1.5 text-xs">
                {STATES.map(([name, desc]) => (
                  <li key={name}><span className="font-medium text-text">{name}:</span> <span className="text-muted">{desc}</span></li>
                ))}
              </ul>
            </Panel>
          </div>
          {canTrace && arch.data.status !== "design" && <div className="lg:col-span-2"><TracePanel /></div>}
        </div>
      )}
    </div>
  );
}
