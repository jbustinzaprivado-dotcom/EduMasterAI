import { useQuery } from "@tanstack/react-query";
import { Bot, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Offering } from "../courses/api";
import { KIND_META, RecommendationCard, type Recommendation } from "./RecommendationCard";

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

export function RecommendationsPage() {
  const { can } = useAuth();
  const student = can("learning") && !can("course.read.all");
  const [history, setHistory] = useState(false);
  const recs = useMyRecommendations(undefined, history, can("learning") && !can("course.read.all"));

  if (!student) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader title="Recomendaciones" description="Motor reglas-v1 (D27): sugerencias explicadas para cada estudiante y su retroalimentación." />
        {(can("ml.read") || can("course.read.all")) ? (
          <Panel title="Aceptación y utilidad por tipo" subtitle="Agregado de tu institución"><MetricsTable /></Panel>
        ) : (
          <Panel><p className="text-sm text-muted">Las recomendaciones de tu grupo aparecen en el detalle de cada curso.</p></Panel>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Mis recomendaciones" description="Sugerencias según tu avance, tus entregas y tus notas. Cada una explica por qué."
        actions={<Button variant="ghost" onClick={() => setHistory((v) => !v)}>{history ? "Ver solo vigentes" : "Ver historial"}</Button>} />
      {recs.isPending && <Skeleton className="h-64" />}
      {recs.isError && <ErrorState error={recs.error} onRetry={() => recs.refetch()} />}
      {recs.data?.length === 0 && <EmptyState icon={Sparkles} title="¡Todo al día!" description="No hay sugerencias pendientes en tus cursos." />}
      <div className="flex flex-col gap-3">{recs.data?.map((r) => <RecommendationCard key={r.id} r={r} />)}</div>
      <p className="mt-4 text-[11px] text-muted">Las recomendaciones son orientativas; tu docente puede verlas y su criterio prevalece (§4.5).</p>
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
              {recs.data.slice(0, 3).map((r) => <RecommendationCard key={r.id} r={r} />)}
              <p className="text-[11px] text-muted">Motor <Badge tone="muted">{recs.data[0]?.source}</Badge> · orientativo, no reemplaza a tu docente.</p>
            </>
          ))}
        </div>
      )}
    </div>
  );
}
