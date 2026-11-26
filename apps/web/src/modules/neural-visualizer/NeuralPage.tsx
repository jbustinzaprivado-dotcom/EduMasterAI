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

/**
 * Selector del visualizador unificado (D52): sin estudiante se ve la arquitectura; con «Todos» o una persona, la
 * misma red se recorre con datos reales. Solo para quien ve el riesgo nominal (docente, administración, auditoría).
 */
function TraceSelector({ offeringId, enrollment, onChange }: {
  offeringId: string | null;
  enrollment: string | null;
  onChange: (next: { oferta?: string | null; matricula?: string | null }) => void;
}) {
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const roster = useQuery({
    queryKey: ["roster", offeringId],
    queryFn: () => api<RosterRow[]>(`/offerings/${offeringId}/enrollments`),
    enabled: !!offeringId,
  });
  return (
    <div className="flex flex-wrap gap-2">
      <label className="sr-only" htmlFor="trace-offering">Oferta</label>
      <select id="trace-offering" className="field w-auto py-1.5 text-xs" value={offeringId ?? ""}
        onChange={(e) => onChange({ oferta: e.target.value || null, matricula: null })}>
        <option value="">Elige una oferta…</option>
        {(offerings.data ?? []).filter((o) => o.status === "active").map((o) => (
          <option key={o.id} value={o.id}>{o.course_code} · {o.course_title} ({o.cohort})</option>
        ))}
      </select>
      <label className="sr-only" htmlFor="trace-student">Estudiante</label>
      <select id="trace-student" className="field w-auto py-1.5 text-xs" value={enrollment ?? ""} disabled={!offeringId}
        onChange={(e) => onChange({ matricula: e.target.value || null })}>
        <option value="">Ver la arquitectura</option>
        <option value="todos">Todos los estudiantes (promedio)</option>
        {(roster.data ?? []).filter((r) => r.status === "active").map((r) => (
          <option key={r.enrollment_id} value={r.enrollment_id}>{r.student_name}</option>
        ))}
      </select>
    </div>
  );
}

export function NeuralPage() {
  const arch = useArchitecture();
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const canTrace = can("assessment.manage") || can("audit.read");
  const offeringId = params.get("oferta");
  const enrollment = params.get("matricula");
  const published = arch.data && arch.data.status !== "design";
  const tracing = canTrace && published && !!enrollment;
  const update = (next: Record<string, string | null | undefined>) => {
    const p = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => { if (v === undefined) return; if (v) p.set(k, v); else p.delete(k); });
    setParams(p, { replace: true });
  };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Arquitectura neuronal" description="Visualizador de §4.10: topología y estado del modelo publicado; con un estudiante o el grupo, el recorrido real de la predicción." />
      {arch.isPending && <Skeleton className="h-96" />}
      {arch.isError && <ErrorState error={arch.error} onRetry={() => arch.refetch()} />}
      {arch.data && (
        <div className={tracing ? "flex flex-col gap-4" : "grid gap-4 lg:grid-cols-[1fr_300px]"}>
          <Panel glow title={tracing ? `${arch.data.model_name} · recorrido real` : arch.data.model_name}
            subtitle={tracing
              ? "La señal avanza capa por capa con los datos actuales; se muestran las neuronas que más aportaron."
              : canTrace && published
                ? `${arch.data.note} Elige una oferta y un estudiante (o todos) para ver el recorrido real.`
                : arch.data.note}
            actions={canTrace && published ? <TraceSelector offeringId={offeringId} enrollment={enrollment} onChange={update} /> : undefined}>
            {tracing
              ? <TraceView arch={arch.data} offeringId={offeringId} enrollment={enrollment!} />
              : <NeuralNetwork arch={arch.data} />}
          </Panel>
          <div className={tracing ? "grid gap-4 md:grid-cols-2" : "flex flex-col gap-4"}>
            <Panel title="Estado del modelo"><ModelStatus arch={arch.data} /></Panel>
            <Panel title="Estados que distinguirá la interfaz" subtitle="Principio de transparencia (§1)">
              <ul className="space-y-1.5 text-xs">
                {STATES.map(([name, desc]) => (
                  <li key={name}><span className="font-medium text-text">{name}:</span> <span className="text-muted">{desc}</span></li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
