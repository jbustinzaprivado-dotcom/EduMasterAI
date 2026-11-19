import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, CheckCircle2, Play, ShieldCheck, Undo2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";

interface Metrics { roc_auc: number; pr_auc: number; f1: number; precision: number; recall: number; brier: number; threshold: number; positive_rate: number }
interface Card {
  kind: string;
  task: string;
  created_at: string;
  dataset: { name: string; version: string; rows: number; label: string; population: string; sha256: string;
    split: Record<string, unknown> & { method: string } };
  selection: { criterion: string; chosen: string; network_wins: boolean };
  results: Record<string, { validation: Metrics; test: Metrics }>;
  segments_test: Record<string, Metrics>;
  calibration_test: { bin: string; n: number; mean_predicted: number; observed_rate: number }[];
  limitations: string[];
  training_history: { epoch: number; val_pr_auc: number }[];
}
interface ModelOut { id: string; name: string; version: string; kind: string; dataset_version: string; threshold: number;
  registered_at: string; published_here: boolean; card: Card }

const MODEL_LABEL: Record<string, string> = {
  logistic_regression: "Regresión logística (baseline)",
  gradient_boosting: "Gradient Boosting (baseline)",
  multitask_gru: "Red multitarea con GRU",
};

const pct = (x: number) => `${(x * 100).toFixed(1)} %`;

function ModelCard({ m }: { m: ModelOut }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const [retiring, setRetiring] = useState(false);
  const [reason, setReason] = useState("");
  const retire = useMutation({
    mutationFn: () => api(`/ml/models/${m.id}/retire`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: () => {
      setRetiring(false);
      setReason("");
      qc.invalidateQueries({ queryKey: ["ml"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
  const approve = useMutation({
    mutationFn: () => api(`/ml/models/${m.id}/approve`, { method: "POST", body: JSON.stringify({ note: "Model card revisada" }) }),
    onSuccess: () => {
      setConfirm(false);
      qc.invalidateQueries({ queryKey: ["ml"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
  const run = useMutation({
    mutationFn: () => api<{ predictions: number; high_risk: number }>("/ml/predictions/run", { method: "POST", body: "{}" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ml"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["risk"] });
    },
  });
  const c = m.card;
  const split = c.dataset.split as Record<string, { rows: number; positive_rate: number }> & { method: string };

  return (
    <div className="flex flex-col gap-4">
      <Panel glow title={`${m.name} · v${m.version}`} subtitle={`${c.task} · registrado ${formatDateTime(m.registered_at)}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {m.published_here ? <Badge tone="teal"><CheckCircle2 className="size-3" /> Publicado en tu institución</Badge>
              : <Badge tone="warning">Candidato · requiere aprobación</Badge>}
            {can("ml.approve") && !m.published_here && (
              <Button icon={ShieldCheck} onClick={() => setConfirm(true)}>Aprobar publicación</Button>
            )}
            {can("ml.approve") && m.published_here && (
              <Button variant="ghost" icon={Undo2} onClick={() => setRetiring(true)}>Retirar</Button>
            )}
            {can("ml.manage") && m.published_here && (
              <Button variant="ghost" icon={Play} loading={run.isPending} onClick={() => run.mutate()}>Ejecutar predicciones</Button>
            )}
          </div>
        }>
        {confirm && (
          <div className="mb-4 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm">
            <p className="font-medium text-warning">¿Aprobar el uso de este modelo en tu institución?</p>
            <p className="mt-1 text-xs text-muted">Verifica métricas, segmentos y limitaciones. Las alertas serán de apoyo al
              docente, nunca sanciones (§9.8). La aprobación queda en la bitácora.</p>
            <div className="mt-2 flex gap-2">
              <Button loading={approve.isPending} onClick={() => approve.mutate()}>Sí, aprobar</Button>
              <Button variant="ghost" onClick={() => setConfirm(false)}>Cancelar</Button>
            </div>
          </div>
        )}
        {retiring && (
          <div className="mb-4 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm">
            <p className="font-medium text-danger">¿Retirar este modelo de tu institución?</p>
            <p className="mt-1 text-xs text-muted">Es la vuelta atrás (rollback): no se generarán alertas nuevas hasta aprobar
              otra versión. Las predicciones ya hechas se conservan como historial. Queda en la bitácora.</p>
            <label className="label mt-2" htmlFor={`retire-${m.id}`}>Motivo (obligatorio)</label>
            <input id={`retire-${m.id}`} className="field" value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="p. ej. métricas por debajo del umbral en la cohorte actual" />
            <div className="mt-2 flex gap-2">
              <Button variant="danger" disabled={reason.trim().length < 5} loading={retire.isPending} onClick={() => retire.mutate()}>Sí, retirar</Button>
              <Button variant="ghost" onClick={() => setRetiring(false)}>Cancelar</Button>
            </div>
            {retire.isError && <p role="alert" className="mt-2 text-danger">{retire.error instanceof ApiError ? retire.error.message : "Error"}</p>}
          </div>
        )}
        {approve.isError && <p role="alert" className="mb-2 text-sm text-danger">{approve.error instanceof ApiError ? approve.error.message : "Error"}</p>}
        {run.isSuccess && <p className="mb-2 text-sm text-teal">{run.data.predictions} predicciones generadas · {run.data.high_risk} con riesgo alto.</p>}
        {run.isError && <p role="alert" className="mb-2 text-sm text-danger">{run.error instanceof ApiError ? run.error.message : "Error"}</p>}

        <p className="mb-2 text-xs text-muted">Comparación en el conjunto de <b>prueba</b> (cohortes más recientes, nunca usadas para elegir):</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="py-2 pr-3 font-medium">Modelo</th><th className="py-2 pr-3 font-medium">PR-AUC val.</th>
                <th className="py-2 pr-3 font-medium">ROC-AUC</th><th className="py-2 pr-3 font-medium">PR-AUC</th>
                <th className="py-2 pr-3 font-medium">F1</th><th className="py-2 pr-3 font-medium">Recall</th>
                <th className="py-2 font-medium">Brier ↓</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {Object.entries(c.results).map(([name, r]) => (
                <tr key={name} className={cx(name === c.selection.chosen && "bg-primary/10")}>
                  <td className="py-2 pr-3">{MODEL_LABEL[name] ?? name}{name === c.selection.chosen && <Badge tone="cyan">elegido</Badge>}</td>
                  <td className="py-2 pr-3 text-muted">{r.validation.pr_auc.toFixed(3)}</td>
                  <td className="py-2 pr-3">{r.test.roc_auc.toFixed(3)}</td>
                  <td className="py-2 pr-3">{r.test.pr_auc.toFixed(3)}</td>
                  <td className="py-2 pr-3">{r.test.f1.toFixed(3)}</td>
                  <td className="py-2 pr-3">{r.test.recall.toFixed(3)}</td>
                  <td className="py-2">{r.test.brier.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted"><b>Regla de selección:</b> {c.selection.criterion}</p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Dataset" subtitle="Ficha (datasheet) · §8">
          <dl className="space-y-1.5 text-xs">
            <div><dt className="text-muted">Versión</dt><dd>{c.dataset.name} {c.dataset.version} <Badge tone="warning">DEMO sintético</Badge></dd></div>
            <div><dt className="text-muted">Filas</dt><dd>{c.dataset.rows.toLocaleString("es-PE")}</dd></div>
            <div><dt className="text-muted">Separación</dt><dd>{split.method}</dd></div>
            {(["train", "val", "test"] as const).map((k) => split[k] && (
              <div key={k}><dt className="text-muted">{k}</dt><dd>{split[k].rows} filas · {pct(split[k].positive_rate)} positivos</dd></div>
            ))}
            <div><dt className="text-muted">Etiqueta</dt><dd>{c.dataset.label}</dd></div>
            <div><dt className="text-muted">Huella SHA-256</dt><dd className="truncate font-mono text-[10px]" title={c.dataset.sha256}>{c.dataset.sha256}</dd></div>
          </dl>
        </Panel>
        <Panel title="Calibración (prueba)" subtitle="Probabilidad predicha vs. tasa observada">
          <ul className="space-y-2 text-xs">
            {c.calibration_test.map((b) => (
              <li key={b.bin}>
                <div className="flex justify-between text-muted"><span>{b.bin} · {b.n} casos</span>
                  <span>pred. {pct(b.mean_predicted)} · obs. {pct(b.observed_rate)}</span></div>
                <div className="relative mt-1 h-1.5 rounded-full bg-surface-2">
                  <div className="absolute h-full rounded-full bg-primary" style={{ width: pct(b.mean_predicted) }} />
                  <div className="absolute top-[-3px] h-3 w-0.5 bg-teal" style={{ left: pct(b.observed_rate) }} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">Barra azul: predicho · línea verde: observado. Cerca = probabilidades honestas.</p>
        </Panel>
        <Panel title="Por segmento (prueba)" subtitle="Nivel del curso · §9.6 paso 15">
          <ul className="space-y-2 text-sm">
            {Object.entries(c.segments_test).map(([seg, s]) => (
              <li key={seg} className="flex justify-between"><span className="capitalize text-muted">{seg}</span>
                <span>ROC {s.roc_auc.toFixed(2)} · recall {s.recall.toFixed(2)}</span></li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Limitaciones y uso responsable" subtitle="Model card · §9.8">
        <ul className="list-inside list-disc space-y-1 text-sm text-muted">
          {c.limitations.map((l) => <li key={l}><span className="text-text/90">{l}</span></li>)}
        </ul>
      </Panel>
    </div>
  );
}

export function ModelsPage() {
  const models = useQuery({ queryKey: ["ml", "models"], queryFn: () => api<ModelOut[]>("/ml/models") });
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Modelos de IA" description="Registro de versiones (§9.6): métricas, dataset, calibración y aprobación humana antes de usarlo." />
      {models.isPending && <Skeleton className="h-96" />}
      {models.isError && <ErrorState error={models.error} onRetry={() => models.refetch()} />}
      {models.data?.length === 0 && <EmptyState icon={BrainCircuit} title="Sin modelos" description="Entrena uno con ml/ y reinicia la API." />}
      <div className="flex flex-col gap-6">{models.data?.map((m) => <ModelCard key={m.id} m={m} />)}</div>
    </div>
  );
}
