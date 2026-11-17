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
}

# (nombre visible, descripción, permisos)
ROLES: dict[str, tuple[str, str, list[str]]] = {
    "superadmin": (
        "Superadministrador",
        "Gobierno global de la plataforma.",
        ["platform.global", "org.read", "org.manage", "user.read", "user.manage", "role.read",
         "audit.read", "dashboard.read"],
    ),
    "admin": (
        "Administrador institucional",
        "Operación de una institución.",
        ["org.read", "user.read", "user.manage", "role.read", "audit.read", "dashboard.read"],
    ),
    "coordinador": (
        "Director / coordinador",
        "Seguimiento académico.",
        ["org.read", "user.read", "role.read", "audit.read.own", "dashboard.read"],
    ),
    "docente": (
        "Docente / instructor",
        "Gestión de enseñanza.",
        ["org.read", "audit.read.own", "dashboard.read"],
    ),
    "estudiante": (
        "Estudiante",
        "Aprendizaje personal.",
        ["org.read", "audit.read.own", "dashboard.read"],
    ),
    "analista": (
        "Analista de datos",
        "Analítica y dataset.",
        ["org.read", "audit.read.own", "dashboard.read"],
    ),
    "ml_engineer": (
        "Científico de datos / ML Engineer",
        "Ciclo de vida del modelo.",
        ["org.read", "audit.read.own", "dashboard.read"],
    ),
    "auditor": (
        "Auditor",
        "Control y cumplimiento, solo lectura.",
        ["org.read", "user.read", "role.read", "audit.read", "dashboard.read"],
    ),
}

# Roles que solo el superadministrador puede asignar.
GLOBAL_ROLES = {"superadmin"}
