import { PageHeader, Panel, ErrorState, Skeleton } from "../../components/ui";
import { ModelStatus, NeuralNetwork, useArchitecture } from "./NeuralNetwork";

const STATES = [
  ["Detenido", "Sin proceso activo."],
  ["Cargando datos", "Lectura del dataset versionado."],
  ["Entrenando", "Retropropagación real (pulsos de derecha a izquierda)."],
  ["Validando", "Métricas sobre el conjunto de validación temporal."],
  ["Publicado", "Versión aprobada en el registro de modelos."],
  ["Inferencia activa", "Propagación hacia delante con datos reales."],
  ["Error", "Fallo del proceso con su correlation_id."],
];

export function NeuralPage() {
  const arch = useArchitecture();
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
        </div>
      )}
    </div>
  );
}
