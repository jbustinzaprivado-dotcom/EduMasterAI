import { CircleDot } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";
import { ACTION_TONE, useActivity } from "./activity";

const ACTIONS: [string, string][] = [
  ["", "Todas las acciones"],
  ["auth.login", "Inicios de sesión"],
  ["auth.login_failed", "Intentos fallidos"],
  ["auth.logout", "Cierres de sesión"],
  ["user.created", "Usuarios creados"],
  ["user.updated", "Usuarios modificados"],
  ["user.roles_changed", "Cambios de rol"],
  ["org.created", "Instituciones creadas"],
];

export function ActivityPage() {
  const { can } = useAuth();
  const [action, setAction] = useState("");
  const query = useActivity(action, 25);
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const scope = can("platform.global") ? "toda la plataforma" : can("audit.read") ? "tu institución" : "tu propia actividad";

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Actividad y auditoría"
        description={`Bitácora de solo lectura (§11.1). Estás viendo ${scope}.`}
        actions={
          <select className="field w-56" value={action} onChange={(e) => setAction(e.target.value)} aria-label="Filtrar por acción">
            {ACTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        } />
      <Panel>
        {query.isPending && <Skeleton className="h-64" />}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
        {query.isSuccess && items.length === 0 && (
          <EmptyState icon={CircleDot} title="Sin registros" description="No hay acciones que coincidan con el filtro." />
        )}
        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-3 font-medium">Fecha</th>
                  <th className="py-2 pr-3 font-medium">Actor</th>
                  <th className="py-2 pr-3 font-medium">Acción</th>
                  <th className="py-2 pr-3 font-medium">Detalle</th>
                  <th className="py-2 pr-3 font-medium">IP</th>
                  <th className="py-2 font-medium">Correlación</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {items.map((a) => (
                  <tr key={a.id} className="align-top">
                    <td className="py-2.5 pr-3 whitespace-nowrap text-muted">{formatDateTime(a.occurred_at)}</td>
                    <td className="py-2.5 pr-3">{a.actor_name ?? <span className="text-muted">No identificado</span>}</td>
                    <td className="py-2.5 pr-3"><Badge tone={ACTION_TONE[a.action] ?? "muted"}>{a.label}</Badge></td>
                    <td className="max-w-xs py-2.5 pr-3 font-mono text-[11px] break-words text-muted">
                      {a.details ? JSON.stringify(a.details) : "—"}
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-[11px] text-muted">{a.ip ?? "—"}</td>
                    <td className="py-2.5 font-mono text-[11px] text-muted" title={a.correlation_id ?? ""}>
                      {a.correlation_id?.slice(0, 8) ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {query.hasNextPage && (
          <div className="mt-4 flex justify-center">
            <Button variant="ghost" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
              Cargar más
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}
