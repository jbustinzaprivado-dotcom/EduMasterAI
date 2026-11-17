import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ApiError, api, type Organization } from "../../lib/api";
import { Badge, Button, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";

export function OrganizationsPage() {
  const qc = useQueryClient();
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: () => api<Organization[]>("/organizations") });
  const [code, setCode] = useState("");
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: () => api<Organization>("/organizations", { method: "POST", body: JSON.stringify({ code, name }) }),
    onSuccess: () => {
      setCode("");
      setName("");
      qc.invalidateQueries({ queryKey: ["organizations"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Instituciones" description="Cada institución tiene sus datos aislados (multi-tenant, decisión D04)." />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Panel title="Registradas">
          {orgs.isPending && <Skeleton className="h-40" />}
          {orgs.isError && <ErrorState error={orgs.error} onRetry={() => orgs.refetch()} />}
          <ul className="divide-y divide-line">
            {orgs.data?.map((o) => (
              <li key={o.id} className="flex items-center gap-3 py-3">
                <Building2 className="size-5 text-cyan" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{o.name}</p>
                  <p className="text-xs text-muted">{o.code} · {o.timezone}</p>
                </div>
                {o.is_platform ? <Badge tone="violet">Plataforma</Badge> : <Badge tone={o.status === "active" ? "teal" : "danger"}>{o.status === "active" ? "Activa" : "Suspendida"}</Badge>}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Nueva institución">
          <form onSubmit={submit} className="flex flex-col gap-3">
            <div>
              <label className="label" htmlFor="o-code">Código (letras, números, - y _)</label>
              <input id="o-code" className="field uppercase" value={code} onChange={(e) => setCode(e.target.value)} required pattern="[A-Za-z0-9_\-]{2,32}" />
            </div>
            <div>
              <label className="label" htmlFor="o-name">Nombre</label>
              <input id="o-name" className="field" value={name} onChange={(e) => setName(e.target.value)} required minLength={3} />
            </div>
            {create.isError && (
              <p role="alert" className="text-sm text-danger">
                {create.error instanceof ApiError ? create.error.message : "No se pudo crear."}
              </p>
            )}
            {create.isSuccess && <p className="text-sm text-teal">Institución creada y auditada.</p>}
            <Button type="submit" icon={Plus} loading={create.isPending} disabled={code.length < 2 || name.length < 3}>Crear</Button>
          </form>
        </Panel>
      </div>
    </div>
  );
}
