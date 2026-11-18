import { useQuery } from "@tanstack/react-query";
import { Bell, ChevronsLeft, LogOut, Menu, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { MODULES, type ModuleDef } from "../../app/modules";
import { ROLE_LABELS, useAuth } from "../../lib/auth";
import { formatTime } from "../../lib/format";
import { Badge, cx } from "../ui";

function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 px-1">
      <img src="/favicon.svg" alt="" className="size-8" />
      {!compact && (
        <div className="leading-tight">
          <p className="text-[15px] font-bold tracking-tight">
            EduMaster<span className="text-cyan">.ai</span>
          </p>
          <p className="text-[9px] font-medium uppercase tracking-[0.18em] text-muted">Aprende · Practica · Destaca</p>
        </div>
      )}
    </div>
  );
}

function useVisibleModules(): ModuleDef[] {
  const { can } = useAuth();
  return MODULES.filter((m) => can(m.permission));
}

function Sidebar({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const modules = useVisibleModules();
  const sections = ["Aprendizaje", "Inteligencia", "Gestión"] as const;
  return (
    <nav aria-label="Módulos" className="flex flex-1 flex-col gap-4 overflow-y-auto px-2 py-2">
      {sections.map((section) => {
        const items = modules.filter((m) => m.section === section);
        if (!items.length) return null;
        return (
          <div key={section}>
            {!collapsed && (
              <p className="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted/80">{section}</p>
            )}
            <ul className="flex flex-col gap-0.5">
              {items.map((m) => (
                <li key={m.path}>
                  <NavLink
                    to={m.path}
                    end={m.path === "/"}
                    onClick={onNavigate}
                    title={collapsed ? m.label : undefined}
                    className={({ isActive }) =>
                      cx(
                        "group flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13px] transition-colors",
                        isActive
                          ? "bg-primary/15 text-cyan shadow-[inset_2px_0_0_var(--color-cyan)]"
                          : "text-muted hover:bg-surface-2/60 hover:text-text",
                        collapsed && "justify-center",
                      )
                    }
                  >
                    <m.icon className="size-[18px] shrink-0" aria-hidden />
                    {!collapsed && <span className="flex-1 truncate">{m.label}</span>}
                    {!collapsed && !m.ready && (
                      <span className="rounded-full bg-violet/15 px-1.5 text-[10px] text-[#b593ff]">F{m.phase}</span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

/** Estado de conexión real: consulta /health/ready cada 30 s (§5.4: no simular "en vivo"). */
function ConnectionStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const r = await fetch("/api/v1/health/ready");
      if (!r.ok) throw new Error("sin conexión");
      return { at: new Date().toISOString() };
    },
    refetchInterval: 30_000,
    retry: false,
  });
  const ok = health.isSuccess && !health.isError;
  return (
    <div className="hidden items-center gap-2 text-xs text-muted md:flex" aria-live="polite">
      <span className={cx("size-2 rounded-full", ok ? "bg-teal shadow-[0_0_8px_var(--color-teal)]" : "bg-danger")} />
      {ok ? `Conectado · ${formatTime(health.data.at)}` : health.isPending ? "Conectando…" : "Sin conexión"}
    </div>
  );
}

function ModuleSearch() {
  const modules = useVisibleModules();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const results = useMemo(
    () => (q.trim() ? modules.filter((m) => m.label.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 6) : []),
    [q, modules],
  );
  return (
    <div className="relative hidden w-64 lg:block">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        className="field pl-9"
        placeholder="Buscar módulo…"
        aria-label="Buscar módulo"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && results[0]) {
            navigate(results[0].path);
            setQ("");
          }
        }}
      />
      {results.length > 0 && (
        <ul className="panel panel-solid absolute top-11 right-0 left-0 z-30 p-1">
          {results.map((m) => (
            <li key={m.path}>
              <button
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-surface-2"
                onClick={() => {
                  navigate(m.path);
                  setQ("");
                }}
              >
                <m.icon className="size-4 text-cyan" aria-hidden /> {m.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Popover({ button, children }: { button: (toggle: () => void, open: boolean) => ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      {button(() => setOpen((v) => !v), open)}
      {open && <div className="panel panel-solid absolute top-12 right-0 z-30 w-72 p-4">{children}</div>}
    </div>
  );
}

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const current = MODULES.find((m) => (m.path === "/" ? location.pathname === "/" : location.pathname.startsWith(m.path)));
  if (!user) return null;
  const initials = user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("");

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-bg/85 px-4 backdrop-blur sm:px-6">
      <button className="rounded-lg p-2 text-muted hover:text-text lg:hidden" onClick={onMenu} aria-label="Abrir menú">
        <Menu className="size-5" />
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{current?.label ?? "EduMaster.ai"}</p>
        <p className="truncate text-[11px] text-muted">{user.organization.name}</p>
      </div>
      <ConnectionStatus />
      <ModuleSearch />
      <Popover
        button={(toggle, open) => (
          <button onClick={toggle} aria-expanded={open} aria-label="Notificaciones"
            className="rounded-lg border border-line p-2 text-muted hover:text-cyan">
            <Bell className="size-4" />
          </button>
        )}
      >
        <p className="text-sm font-semibold">Centro de notificaciones</p>
        <p className="mt-1 text-xs text-muted">
          Las notificaciones en tiempo real (WebSocket/SSE) se construyen en la Fase 3. Mientras tanto, la actividad
          registrada está en "Actividad y auditoría".
        </p>
      </Popover>
      <Popover
        button={(toggle, open) => (
          <button onClick={toggle} aria-expanded={open} aria-label="Perfil"
            className="flex size-9 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet text-xs font-bold">
            {initials}
          </button>
        )}
      >
        <p className="text-sm font-semibold">{user.full_name}</p>
        <p className="text-xs text-muted">{user.email}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {user.roles.map((r) => (
            <Badge key={r} tone="cyan">{ROLE_LABELS[r] ?? r}</Badge>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">Institución: {user.organization.code}</p>
        <button onClick={signOut}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-line py-2 text-sm text-muted hover:text-danger">
          <LogOut className="size-4" /> Cerrar sesión
        </button>
      </Popover>
    </header>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-full">
      {/* Escritorio: barra lateral fija y contraíble (§5.2). */}
      <aside className={cx("sticky top-0 hidden h-screen shrink-0 flex-col border-r border-line bg-surface/60 py-4 lg:flex",
        collapsed ? "w-[72px]" : "w-64")}>
        <div className="mb-3 px-3"><Logo compact={collapsed} /></div>
        <Sidebar collapsed={collapsed} />
        <button onClick={() => setCollapsed((v) => !v)}
          className="mx-3 mt-2 flex items-center justify-center gap-2 rounded-lg py-2 text-xs text-muted hover:text-text"
          aria-label={collapsed ? "Expandir menú" : "Contraer menú"}>
          <ChevronsLeft className={cx("size-4 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && "Contraer"}
        </button>
      </aside>

      {/* Móvil: cajón superpuesto. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-line bg-surface py-4">
            <div className="mb-3 flex items-center justify-between px-3">
              <Logo />
              <button onClick={() => setMobileOpen(false)} aria-label="Cerrar menú" className="p-2 text-muted"><X className="size-5" /></button>
            </div>
            <Sidebar collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <main className="flex-1 px-4 py-5 sm:px-6 sm:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
