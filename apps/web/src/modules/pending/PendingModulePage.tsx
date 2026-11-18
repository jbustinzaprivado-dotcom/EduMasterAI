import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { PHASES, type ModuleDef } from "../../app/modules";
import { Badge, PageHeader, Panel, cx } from "../../components/ui";

/** Página de un módulo aún no construido: muestra su alcance y en qué fase llega, sin datos ficticios. */
export function PendingModulePage({ module: m }: { module: ModuleDef }) {
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={m.label} description={m.summary} actions={<Badge tone="violet">Se construye en la Fase {m.phase}</Badge>} />
      <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
        <Panel title="Qué incluirá" subtitle={`Especificación ${m.docRef}`}>
          <ul className="space-y-2.5">
            {m.features.map((f) => (
              <li key={f} className="flex gap-2.5 text-sm">
                <m.icon className="mt-0.5 size-4 shrink-0 text-cyan" aria-hidden />
                {f}
              </li>
            ))}
          </ul>
          <p className="mt-5 rounded-xl border border-dashed border-line p-3 text-xs text-muted">
            Este módulo todavía no tiene datos. El documento rector exige que cada indicador y botón esté conectado a un
            servicio real (§1), por eso aquí no se muestran cifras de ejemplo.
          </p>
        </Panel>
        <Panel title="Ubicación en la hoja de ruta">
          <ol className="space-y-2">
            {PHASES.map((p) => (
              <li key={p.n} className="flex items-center gap-2.5 text-sm">
                {p.status === "done" ? <CheckCircle2 className="size-4 text-teal" /> : p.status === "partial" ? <CircleDot className="size-4 text-cyan" /> : <Circle className="size-4 text-muted/50" />}
                <span className={cx(p.n === m.phase ? "font-semibold text-[#b593ff]" : p.status === "partial" ? "text-cyan" : "text-muted")}>
                  {p.n}. {p.name}
                </span>
                {p.n === m.phase && <Badge tone="violet">este módulo</Badge>}
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </div>
  );
}
