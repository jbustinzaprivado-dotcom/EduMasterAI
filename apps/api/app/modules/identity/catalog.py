"""Catálogo de roles y permisos (§3). Es la única fuente: al arrancar se sincroniza con la base.

Los permisos de las fases siguientes (cursos, dataset, modelos) se agregan aquí cuando se construyen.
"""

PERMISSIONS: dict[str, str] = {
    "platform.global": "Ver y operar todas las instituciones",
    "org.read": "Consultar instituciones",
    "org.manage": "Crear y modificar instituciones",
    "user.read": "Consultar usuarios de la institución",
    "user.manage": "Crear usuarios, cambiar estado y roles",
    "role.read": "Consultar roles y permisos",
    "audit.read": "Consultar la bitácora de la institución",
    "audit.read.own": "Consultar la propia actividad",
    "dashboard.read": "Ver el panel de resumen",
    # Fase 2 · core académico
    "course.read.all": "Consultar todos los cursos, ofertas y matrículas de la institución",
    "course.manage": "Crear cursos y ofertas, publicar y matricular",
    "assessment.manage": "Crear evaluaciones y registrar notas oficiales (docente: solo sus ofertas)",
    "learning": "Participar en los cursos donde está matriculado",
    "path.manage": "Crear, publicar y asignar rutas de aprendizaje; autorizar excepciones",
    # Fases 5-6 · IA
    "ml.read": "Consultar modelos, métricas y model cards",
    "ml.manage": "Registrar modelos y ejecutar predicciones",
    "ml.approve": "Aprobar la publicación de un modelo en la institución",
}

# (nombre visible, descripción, permisos)
ROLES: dict[str, tuple[str, str, list[str]]] = {
    "superadmin": (
        "Superadministrador",
        "Gobierno global de la plataforma.",
        ["platform.global", "org.read", "org.manage", "user.read", "user.manage", "role.read",
         "audit.read", "dashboard.read", "course.read.all", "course.manage", "assessment.manage",
         "ml.read", "ml.manage", "ml.approve", "path.manage"],
    ),
    "admin": (
        "Administrador institucional",
        "Operación de una institución.",
        ["org.read", "user.read", "user.manage", "role.read", "audit.read", "dashboard.read",
         "course.read.all", "course.manage", "assessment.manage", "ml.read", "ml.approve", "path.manage"],
    ),
    "coordinador": (
        "Director / coordinador",
        "Seguimiento académico.",
        ["org.read", "user.read", "role.read", "audit.read.own", "dashboard.read",
         "course.read.all", "course.manage", "assessment.manage", "ml.read", "path.manage"],
    ),
    "docente": (
        "Docente / instructor",
        "Gestión de enseñanza.",
        ["org.read", "audit.read.own", "dashboard.read", "assessment.manage"],
    ),
    "estudiante": (
        "Estudiante",
        "Aprendizaje personal.",
        ["org.read", "audit.read.own", "dashboard.read", "learning"],
    ),
    "analista": (
        "Analista de datos",
        "Analítica y dataset.",
        ["org.read", "audit.read.own", "dashboard.read", "course.read.all", "ml.read"],
    ),
    "ml_engineer": (
        "Científico de datos / ML Engineer",
        "Ciclo de vida del modelo.",
        ["org.read", "audit.read.own", "dashboard.read", "ml.read", "ml.manage"],
    ),
    "auditor": (
        "Auditor",
        "Control y cumplimiento, solo lectura.",
        ["org.read", "user.read", "role.read", "audit.read", "dashboard.read", "course.read.all", "ml.read"],
    ),
}

# Roles que solo el superadministrador puede asignar.
GLOBAL_ROLES = {"superadmin"}
