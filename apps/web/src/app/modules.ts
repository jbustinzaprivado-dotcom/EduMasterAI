import {
  Activity,
  Award,
  BrainCircuit,
  BarChart3,
  BookOpen,
  Bot,
  Building2,
  ClipboardCheck,
  Gauge,
  Grid3x3,
  LayoutDashboard,
  MessagesSquare,
  Network,
  Route,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

/** Catálogo de módulos de §4. `phase` es la fase de §14 en que el módulo queda operativo;
 *  `ready` indica si ya funciona. Los pendientes muestran su plan, nunca datos inventados. */
export interface ModuleDef {
  path: string;
  label: string;
  icon: LucideIcon;
  section: "Aprendizaje" | "Inteligencia" | "Gestión";
  phase: number;
  ready: boolean;
  permission: string;
  docRef: string;
  summary: string;
  features: string[];
}

export const MODULES: ModuleDef[] = [
  {
    path: "/", label: "Resumen", icon: LayoutDashboard, section: "Aprendizaje", phase: 1, ready: true,
    permission: "dashboard.read", docRef: "§4.1",
    summary: "KPIs con valor, variación, fuente y fecha de actualización.",
    features: [],
  },
  {
    path: "/rutas", label: "Rutas de aprendizaje", icon: Route, section: "Aprendizaje", phase: 2, ready: true,
    permission: "dashboard.read", docRef: "§4.2",
    summary: "Secuencias de cursos con objetivos, competencias y prerrequisitos.",
    features: ["Crear rutas con duración y criterios de logro", "Asignar por estudiante, grupo o cohorte",
      "Avance por etapa y fecha objetivo", "Historial de cambios de ruta"],
  },
  {
    path: "/cursos", label: "Cursos", icon: BookOpen, section: "Aprendizaje", phase: 2, ready: true,
    permission: "dashboard.read", docRef: "§4.3",
    summary: "Catálogo de cursos, unidades, lecciones y recursos con versionado.",
    features: ["Código, nivel, docente, fechas, etiquetas y competencias", "Unidades, lecciones y archivos",
      "Control de publicación y versiones", "Búsqueda, filtros, importación y exportación"],
  },
  {
    path: "/evaluaciones", label: "Evaluaciones", icon: ClipboardCheck, section: "Aprendizaje", phase: 2,
    ready: true, permission: "dashboard.read", docRef: "§4.6",
    summary: "Bancos de preguntas, rúbricas, intentos y ponderaciones.",
    features: ["Opción múltiple, V/F, respuesta corta, archivo y práctica", "Registro de intentos",
      "Nota oficial separada de la estimación de IA", "Reglas de evaluación por curso"],
  },
  {
    path: "/certificados", label: "Certificados", icon: Award, section: "Aprendizaje", phase: 3, ready: true,
    permission: "dashboard.read", docRef: "§4.7",
    summary: "Emisión con folio único, PDF y código QR verificable.",
    features: ["Plantillas configurables", "Estados borrador, emitido, anulado y expirado",
      "Portal público de verificación con datos mínimos", "Auditoría de emisión y anulación"],
  },
  {
    path: "/comunidad", label: "Comunidad", icon: MessagesSquare, section: "Aprendizaje", phase: 3, ready: true,
    permission: "dashboard.read", docRef: "§4.8",
    summary: "Anuncios, debates y comentarios por curso con moderación.",
    features: ["Espacios por curso", "Moderación y reportes", "Preferencias de notificación"],
  },
  {
    path: "/analitica", label: "Analítica", icon: BarChart3, section: "Inteligencia", phase: 4, ready: true,
    permission: "analytics.read", docRef: "§4.4",
    summary: "Participación, progreso, finalización y tendencias según permisos.",
    features: ["Panel por institución, curso, cohorte y estudiante", "Definición documentada de cada indicador",
      "Exportación CSV/XLSX/PDF auditada"],
  },
  {
    path: "/habilidades", label: "Dominio de habilidades", icon: Grid3x3, section: "Inteligencia", phase: 4,
    ready: true, permission: "dashboard.read", docRef: "§4.9",
    summary: "Heatmap de competencias en 5 niveles de dominio.",
    features: ["Catálogo jerárquico de competencias", "Evidencia por actividad",
      "Nivel estimado por IA separado del validado por el docente"],
  },
  {
    path: "/red-neuronal", label: "Red neuronal", icon: Network, section: "Inteligencia", phase: 1, ready: true,
    permission: "dashboard.read", docRef: "§4.10",
    summary: "Topología del modelo multitarea; estados reales desde la Fase 5.",
    features: [],
  },
  {
    path: "/modelos", label: "Modelos de IA", icon: BrainCircuit, section: "Inteligencia", phase: 5, ready: true,
    permission: "ml.read", docRef: "§9",
    summary: "Versiones, métricas, model card y aprobación de publicación.",
    features: [],
  },
  {
    path: "/tutor", label: "IA Tutor", icon: Bot, section: "Inteligencia", phase: 6, ready: true,
    permission: "dashboard.read", docRef: "§4.5",
    summary: "Sugerencias de recursos y actividades según brechas de competencia.",
    features: ["Motivo explicado de cada sugerencia", "Aceptar, descartar o marcar como útil",
      "Revisión del docente"],
  },
  {
    path: "/recomendaciones", label: "Recomendaciones", icon: Sparkles, section: "Inteligencia", phase: 6,
    ready: true, permission: "dashboard.read", docRef: "§4.11",
    summary: "Acciones priorizadas con impacto esperado y estado.",
    features: ["Estados nueva, aceptada, descartada, completada y expirada",
      "Medición de aceptación y utilidad, no solo clics"],
  },
  {
    path: "/actividad", label: "Actividad y auditoría", icon: Activity, section: "Gestión", phase: 1, ready: true,
    permission: "dashboard.read", docRef: "§4.12, §11.1",
    summary: "Feed de acciones registradas en la bitácora.",
    features: [],
  },
  {
    path: "/administracion/usuarios", label: "Usuarios y roles", icon: Users, section: "Gestión", phase: 1,
    ready: true, permission: "user.read", docRef: "§3, §4.13",
    summary: "Altas, estados y roles de la institución.",
    features: [],
  },
  {
    path: "/administracion/instituciones", label: "Instituciones", icon: Building2, section: "Gestión", phase: 1,
    ready: true, permission: "org.manage", docRef: "§3",
    summary: "Instituciones de la plataforma (multi-tenant).",
    features: [],
  },
  {
    path: "/operacion", label: "Operación", icon: Gauge, section: "Gestión", phase: 7, ready: true,
    permission: "ops.read", docRef: "§12.1",
    summary: "Latencia, errores, conexiones en vivo y frescura de datos frente a los objetivos de §10.5.",
    features: [],
  },
];

export type PhaseStatus = "done" | "partial" | "pending";

/** Fases de §14 con su avance real (ver docs/fase-0/backlog.md). */
export const PHASES: { n: number; name: string; status: PhaseStatus; note?: string }[] = [
  { n: 0, name: "Descubrimiento", status: "done" },
  { n: 1, name: "Fundaciones", status: "done" },
  { n: 2, name: "Core académico", status: "done", note: "cursos, evaluaciones y rutas" },
  { n: 3, name: "Dashboard y tiempo real", status: "done", note: "mapa, notificaciones en vivo, certificados y comunidad" },
  { n: 4, name: "Dataset y analítica", status: "done", note: "dataset DEMO, analítica y dominio de habilidades" },
  { n: 5, name: "Modelo neuronal", status: "done", note: "riesgo de abandono" },
  { n: 6, name: "IA en producto", status: "done", note: "alertas, recomendaciones e IA Tutor (reglas-v1)" },
  { n: 7, name: "Endurecimiento", status: "done", note: "seguridad HTTP, métricas, respaldo, carga y UAT" },
  { n: 8, name: "Producción", status: "done", note: "smoke test, runbooks y rollback (demo por túnel)" },
];
