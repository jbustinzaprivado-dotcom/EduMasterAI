import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, UserCheck, Users, UserX, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ApiError, api, type Organization } from "../../lib/api";
import { ROLE_LABELS, useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";

interface UserRow {
  id: string;
  organization_id: string;
  organization_code: string;
  email: string;
  full_name: string;
  status: "active" | "disabled";
  roles: string[];
  last_login_at: string | null;
  created_at: string;
}

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

interface Role {
  code: string;
  name: string;
  description: string;
  permissions: string[];
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const details = Array.isArray(err.body.details)
      ? (err.body.details as { field?: string; message?: string }[]).map((d) => d.field ? `${d.field}: ${d.message}` : String(d)).join(" · ")
      : "";
    return details ? `${err.message} ${details}` : err.message;
  }
  return "No se pudo completar la acción.";
}

function UserDialog({ user, roles, orgs, onClose }: { user: UserRow | null; roles: Role[]; orgs: Organization[]; onClose: () => void }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selected, setSelected] = useState<string[]>(user?.roles ?? []);
  const [orgId, setOrgId] = useState("");

  const save = useMutation({
    mutationFn: () =>
      user
        ? api<UserRow>(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ full_name: fullName, roles: selected }) })
        : api<UserRow>("/users", {
            method: "POST",
            body: JSON.stringify({ email, full_name: fullName, password, roles: selected, organization_id: orgId || undefined }),
          }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-labelledby="user-dialog-title">
      <form onSubmit={submit} className="panel panel-glow flex max-h-[90vh] w-full max-w-lg flex-col gap-4 overflow-y-auto p-5">
        <div className="flex items-center justify-between">
          <h2 id="user-dialog-title" className="text-base font-semibold">{user ? "Editar usuario" : "Nuevo usuario"}</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="text-muted hover:text-text"><X className="size-5" /></button>
        </div>
        {!user && can("platform.global") && (
          <div>
            <label className="label" htmlFor="u-org">Institución</label>
            <select id="u-org" className="field" value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              <option value="">La mía (plataforma)</option>
              {orgs.filter((o) => !o.is_platform).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor="u-name">Nombre completo</label>
          <input id="u-name" className="field" value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={3} />
        </div>
        {!user && (
          <>
            <div>
              <label className="label" htmlFor="u-email">Correo</label>
              <input id="u-email" type="email" className="field" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="u-pass">Contraseña inicial (mín. 10 caracteres)</label>
              <input id="u-pass" type="password" className="field" value={password} onChange={(e) => setPassword(e.target.value)}
                required minLength={10} autoComplete="new-password" />
            </div>
          </>
        )}
        <fieldset>
          <legend className="label">Roles</legend>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {roles.map((r) => (
              <label key={r.code} className="flex cursor-pointer items-start gap-2 rounded-lg border border-line p-2 text-sm hover:border-cyan/50">
                <input type="checkbox" className="mt-0.5 accent-[var(--color-cyan)]" checked={selected.includes(r.code)}
                  onChange={(e) => setSelected((s) => (e.target.checked ? [...s, r.code] : s.filter((c) => c !== r.code)))} />
                <span>
                  <span className="block">{r.name}</span>
                  <span className="block text-[11px] text-muted">{r.description}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        {save.isError && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{errorText(save.error)}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" loading={save.isPending} disabled={!selected.length}>Guardar</Button>
        </div>
      </form>
    </div>
  );
}

export function UsersPage() {
  const { can, user: me } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<UserRow | null | "new">(null);

  const params = new URLSearchParams({ page: String(page), page_size: "15" });
  if (q.trim()) params.set("q", q.trim());
  if (role) params.set("role", role);

  const users = useQuery({
    queryKey: ["users", q, role, page],
    queryFn: () => api<Page<UserRow>>(`/users?${params}`),
    placeholderData: keepPreviousData,
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/roles") });
  const orgs = useQuery({ queryKey: ["organizations"], queryFn: () => api<Organization[]>("/organizations") });

  const toggleStatus = useMutation({
    mutationFn: (u: UserRow) =>
      api<UserRow>(`/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ status: u.status === "active" ? "disabled" : "active" }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  const manage = can("user.manage");
  const totalPages = users.data ? Math.max(1, Math.ceil(users.data.total / users.data.page_size)) : 1;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Usuarios y roles"
        description={can("platform.global") ? "Todas las instituciones (superadministrador)." : `Solo ${me?.organization.name}. El aislamiento lo aplica el backend.`}
        actions={manage && <Button icon={Plus} onClick={() => setEditing("new")}>Nuevo usuario</Button>} />

      <Panel>
        <div className="mb-4 flex flex-wrap gap-2">
          <input className="field max-w-xs" placeholder="Buscar por nombre o correo…" aria-label="Buscar usuarios"
            value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          <select className="field w-56" value={role} aria-label="Filtrar por rol" onChange={(e) => { setRole(e.target.value); setPage(1); }}>
            <option value="">Todos los roles</option>
            {roles.data?.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
          {users.data && <span className="ml-auto self-center text-xs text-muted">{users.data.total} usuarios</span>}
        </div>

        {users.isPending && <Skeleton className="h-72" />}
        {users.isError && <ErrorState error={users.error} onRetry={() => users.refetch()} />}
        {users.data && users.data.items.length === 0 && (
          <EmptyState icon={Users} title="Sin resultados" description="Ningún usuario coincide con la búsqueda." />
        )}
        {users.data && users.data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-3 font-medium">Usuario</th>
                  {can("platform.global") && <th className="py-2 pr-3 font-medium">Institución</th>}
                  <th className="py-2 pr-3 font-medium">Roles</th>
                  <th className="py-2 pr-3 font-medium">Estado</th>
                  <th className="py-2 pr-3 font-medium">Último acceso</th>
                  {manage && <th className="py-2 font-medium"><span className="sr-only">Acciones</span></th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {users.data.items.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5 pr-3">
                      <p className="font-medium">{u.full_name}</p>
                      <p className="text-xs text-muted">{u.email}</p>
                    </td>
                    {can("platform.global") && <td className="py-2.5 pr-3 text-xs text-muted">{u.organization_code}</td>}
                    <td className="py-2.5 pr-3">
                      <div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} tone="cyan">{ROLE_LABELS[r] ?? r}</Badge>)}</div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge tone={u.status === "active" ? "teal" : "danger"}>{u.status === "active" ? "Activo" : "Desactivado"}</Badge>
                    </td>
                    <td className="py-2.5 pr-3 text-xs text-muted">{formatDateTime(u.last_login_at)}</td>
                    {manage && (
                      <td className="py-2.5 text-right whitespace-nowrap">
                        <Button variant="ghost" icon={Pencil} className="mr-1 px-2 py-1 text-xs" onClick={() => setEditing(u)} aria-label={`Editar ${u.full_name}`} />
                        {u.id !== me?.id && (
                          <Button variant={u.status === "active" ? "danger" : "ghost"} className="px-2 py-1 text-xs"
                            icon={u.status === "active" ? UserX : UserCheck}
                            loading={toggleStatus.isPending && toggleStatus.variables?.id === u.id}
                            onClick={() => toggleStatus.mutate(u)}
                            title={u.status === "active" ? "Desactivar" : "Activar"}
                            aria-label={`${u.status === "active" ? "Desactivar" : "Activar"} a ${u.full_name}`} />
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {toggleStatus.isError && <p role="alert" className="mt-3 text-sm text-danger">{errorText(toggleStatus.error)}</p>}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-end gap-2 text-sm">
            <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
            <span className="text-muted">Página {page} de {totalPages}</span>
            <Button variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
          </div>
        )}
      </Panel>

      {editing && roles.data && (
        <UserDialog user={editing === "new" ? null : editing} roles={roles.data} orgs={orgs.data ?? []} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
