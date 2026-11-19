import { Loader2, ShieldOff } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router";
import { AppShell } from "../components/layout/AppShell";
import { EmptyState } from "../components/ui";
import { useAuth } from "../lib/auth";
import { OrganizationsPage } from "../modules/administration/OrganizationsPage";
import { UsersPage } from "../modules/administration/UsersPage";
import { AnalyticsPage } from "../modules/analytics/AnalyticsPage";
import { OperationsPage } from "../modules/operations/OperationsPage";
import { ActivityPage } from "../modules/audit/ActivityPage";
import { CertificatesPage, VerifyPage } from "../modules/certificates/CertificatesPage";
import { CommunityPage } from "../modules/community/CommunityPage";
import { PathsPage } from "../modules/paths/PathsPage";
import { SkillsPage } from "../modules/skills/SkillsPage";
import { AssessmentsPage } from "../modules/courses/AssessmentsPage";
import { CoursesPage } from "../modules/courses/CoursesPage";
import { OfferingPage } from "../modules/courses/OfferingPage";
import { LoginPage } from "../modules/auth/LoginPage";
import { ForcedPasswordPage, ProfilePage } from "../modules/auth/ProfilePage";
import { LessonPage } from "../modules/courses/LessonPage";
import { DashboardPage } from "../modules/dashboard/DashboardPage";
import { ModelsPage } from "../modules/ml/ModelsPage";
import { RecommendationsPage, TutorPage } from "../modules/recommendations/RecommendationsPage";
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
  if (!user) return <Navigate to="/login" replace />;
  // Contraseña temporal: solo se puede cambiarla (el servidor también bloquea el resto de la API).
  if (user.must_change_password) return <ForcedPasswordPage />;
  return children;
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
  "/modelos": <ModelsPage />,
  "/recomendaciones": <RecommendationsPage />,
  "/tutor": <TutorPage />,
  "/cursos": <CoursesPage />,
  "/evaluaciones": <AssessmentsPage />,
  "/certificados": <CertificatesPage />,
  "/comunidad": <CommunityPage />,
  "/rutas": <PathsPage />,
  "/analitica": <AnalyticsPage />,
  "/habilidades": <SkillsPage />,
  "/actividad": <ActivityPage />,
  "/administracion/usuarios": <UsersPage />,
  "/administracion/instituciones": <OrganizationsPage />,
  "/operacion": <OperationsPage />,
};

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verificar" element={<VerifyPage />} />
      <Route path="/verificar/:code" element={<VerifyPage />} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        {MODULES.map((m) => (
          <Route key={m.path} path={m.path}
            element={<PermissionGate permission={m.permission}>{READY[m.path] ?? <PendingModulePage module={m} />}</PermissionGate>} />
        ))}
        <Route path="/cursos/:offeringId" element={<OfferingPage />} />
        <Route path="/cursos/:offeringId/actividad/:activityId" element={<LessonPage />} />
        <Route path="/perfil" element={<ProfilePage />} />
        <Route path="*" element={
          <div className="pt-10 text-center text-sm text-muted">
            Página no encontrada. <Link to="/" className="text-cyan hover:underline">Volver al resumen</Link>
          </div>
        } />
      </Route>
    </Routes>
  );
}
