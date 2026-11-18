import { Loader2, ShieldOff } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router";
import { AppShell } from "../components/layout/AppShell";
import { EmptyState } from "../components/ui";
import { useAuth } from "../lib/auth";
import { OrganizationsPage } from "../modules/administration/OrganizationsPage";
import { UsersPage } from "../modules/administration/UsersPage";
import { ActivityPage } from "../modules/audit/ActivityPage";
import { AssessmentsPage } from "../modules/courses/AssessmentsPage";
import { CoursesPage } from "../modules/courses/CoursesPage";
import { OfferingPage } from "../modules/courses/OfferingPage";
import { LoginPage } from "../modules/auth/LoginPage";
import { DashboardPage } from "../modules/dashboard/DashboardPage";
import { NeuralPage } from "../modules/neural-visualizer/NeuralPage";
import { PendingModulePage } from "../modules/pending/PendingModulePage";
import { MODULES } from "./modules";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex min-h-full items-center justify-center text-muted">
        <Loader2 className="size-6 animate-spin" aria-label="Cargando sesión" />
      </div>
    );
  return user ? children : <Navigate to="/login" replace />;
}

/** Oculta la ruta si falta el permiso. Es comodidad visual: la seguridad real está en la API (§3). */
function PermissionGate({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  if (can(permission)) return children;
  return (
    <div className="mx-auto max-w-md pt-10">
      <EmptyState icon={ShieldOff} title="Sin permiso" description="Tu rol no tiene acceso a este módulo." />
    </div>
  );
}

const READY: Record<string, ReactNode> = {
  "/": <DashboardPage />,
  "/red-neuronal": <NeuralPage />,
  "/cursos": <CoursesPage />,
  "/evaluaciones": <AssessmentsPage />,
  "/actividad": <ActivityPage />,
  "/administracion/usuarios": <UsersPage />,
  "/administracion/instituciones": <OrganizationsPage />,
};

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        {MODULES.map((m) => (
          <Route key={m.path} path={m.path}
            element={<PermissionGate permission={m.permission}>{READY[m.path] ?? <PendingModulePage module={m} />}</PermissionGate>} />
        ))}
        <Route path="/cursos/:offeringId" element={<OfferingPage />} />
        <Route path="*" element={
          <div className="pt-10 text-center text-sm text-muted">
            Página no encontrada. <Link to="/" className="text-cyan hover:underline">Volver al resumen</Link>
          </div>
        } />
      </Route>
    </Routes>
  );
}
