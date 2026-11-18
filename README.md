# EduMaster.ai

Plataforma empresarial de aprendizaje inteligente: gestión académica, analítica y redes neuronales con
supervisión humana. Proyecto académico grupal construido según la *Especificación funcional y técnica v1.0*
(12-11-2026), citada como **§N**.

> **Estado:** Fases 0, 1, 2, 4, 5 y 6 ✅ · Fase 3 casi completa (faltan mapa y comunidad) · pendientes: rutas,
> ranking aprendido y Fases 7-8.
> La hoja de ruta completa está en [docs/fase-0/backlog.md](docs/fase-0/backlog.md).

## Qué funciona hoy

| Área | Detalle |
|---|---|
| Inicio de sesión | Institución + correo + contraseña. Token de 15 min y sesión renovable con detección de robo. |
| Roles y permisos | Los 8 roles de §3. El backend valida cada petición; ocultar botones es solo comodidad. |
| Multi-institución | Cada institución ve solo sus datos. Probado con pruebas automáticas de aislamiento. |
| Bitácora | Toda acción crítica queda registrada. En PostgreSQL no se puede editar ni borrar. |
| Cursos | Catálogo con unidades y actividades, publicación, ofertas por periodo y cohorte, matrículas. |
| Aprendizaje | El estudiante marca actividades; cada evento es idempotente y recalcula su progreso. |
| Evaluaciones | Pesos que suman hasta 100 %, entregas con control de intentos y plazo, nota oficial del docente (0-20). |
| Panel | KPIs académicos reales con variación, tendencia semanal, finalización, alertas abiertas y actividad. |
| Modelo de IA | Riesgo de abandono: baselines vs. red con GRU, model card, calibración y aprobación por institución. |
| Alertas | El docente ve el riesgo de sus estudiantes con los factores que lo explican y lo marca atendido o descartado. |
| Notificaciones en vivo | Campana con contador y avisos al instante (SSE): notas, evaluaciones, certificados, alertas. |
| Certificados | Emisión automática por criterio oficial, PDF con QR, anulación y verificación pública en `/verificar`. |
| Recomendaciones e IA Tutor | Sugerencias explicadas (siguiente actividad, entrega próxima, reforzar, retomar) con feedback y métricas de utilidad. |
| Administración | Usuarios, roles e instituciones. |
| Operación | Logs JSON con `correlation_id`, health checks, errores normalizados, CI en GitHub Actions. |

Los módulos que aún no existen muestran **qué incluirán y en qué fase llegan**, nunca cifras inventadas (§1).

## Instalar y abrir (Windows)

Requisitos: Python 3.13, Node 24 y Git. PostgreSQL es opcional en local (sin él se usa SQLite).

1. `instalar.bat`: instala todo, crea el `.env` con secretos aleatorios y carga las cuentas DEMO.
2. `iniciar.bat`: abre http://localhost:8000.
3. Opcional: `infra\scripts\crear_base.ps1` pasa la base a PostgreSQL.

### Cuentas DEMO
La contraseña común está en `.env` (`EDUMASTER_DEMO_PASSWORD`). La pantalla de login lista las cuentas.

| Institución | Correo | Rol |
|---|---|---|
| PLATAFORMA | superadmin@edumaster.demo | Superadministrador |
| ANDINO | admin@andino.demo | Administrador institucional |
| ANDINO | coordinacion@andino.demo | Coordinador |
| ANDINO | docente@andino.demo | Docente |
| ANDINO | estudiante@andino.demo | Estudiante |
| ANDINO | analista@andino.demo · ml@andino.demo · auditoria@andino.demo | Analista · ML Engineer · Auditor |
| ANDINO | docente2@andino.demo · estudiante2@ … estudiante13@andino.demo | Más docentes y estudiantes |
| PACIFICO | admin@pacifico.demo · docente@ · estudiante@ | Otra institución (para probar el aislamiento) |

Datos académicos DEMO: PY-101 (casi termina), DS-201 y ML-301 (a mitad de ciclo) y un borrador WEB-110.
La estudiante DEMO `estudiante@andino.demo` tiene un perfil "en riesgo" para mostrar alertas en vivo.

## Demostración pública

`demo.bat` arranca la API en modo demo y abre un **Cloudflare Tunnel**. La dirección `https://…trycloudflare.com`
aparece en la ventana y funciona mientras esta siga abierta (Ctrl+C para cerrar). Requiere `cloudflared`.

## Estructura (§15.1)

```
apps/api/      FastAPI: app/core (config, seguridad, logs), app/modules/<dominio>, migrations, tests
apps/web/      React 19 + TypeScript + Vite + Tailwind: src/modules/<módulo>, src/components
ml/            Generador del dataset DEMO, entrenamiento (PyTorch), registro de modelos y pruebas
infra/scripts/ Instalación, base PostgreSQL y túnel de demostración
docs/          Fase 0, arquitectura, explicación sencilla y bitácora de desarrollo
```

## Desarrollo

```bash
cd apps/api && .venv/Scripts/python -m pytest          # pruebas de la API
cd apps/api && .venv/Scripts/python -m uvicorn app.main:app --reload
cd apps/web && npm run dev                              # web en http://localhost:5173 (reenvía /api)
cd apps/web && npm run typecheck && npm test
cd ml && .venv/Scripts/python -m edumaster_ml.train      # reentrena (requiere ml/requirements.txt + torch)
cd ml && .venv/Scripts/python -m pytest
```

### Guion de la demo de IA
1. `admin@andino.demo` → **Modelos de IA** → revisa la model card → **Aprobar publicación**.
2. `docente@andino.demo` → **Cursos** → PY-101 → **Actualizar riesgo con IA**.
3. Abre la alerta de `Valeria Mendoza` (perfil en riesgo): probabilidad, factores y **Marcar atendida**.
4. **Red neuronal** muestra el modelo publicado, sus métricas y la latencia de la última inferencia.
5. `estudiante@andino.demo` → **IA Tutor** → «¿Qué hago ahora?»: sugerencias con su motivo; acepta o valora una.
6. De vuelta como docente, el curso muestra las **recomendaciones del grupo**.
7. **En vivo:** con Valeria abierta en otra ventana, el docente califica su entrega en **Evaluaciones** y a ella
   le aparece el aviso al instante.
8. **Certificados:** como admin, **Certificados** lista los emitidos (los datos DEMO varían según la fecha de carga);
   descarga un PDF y abre su enlace de verificación: `/verificar/<código>` funciona sin sesión.

Documentación: [cómo funciona (explicación sencilla)](docs/como-funciona.md) ·
[decisiones](docs/fase-0/decisiones.md) · [bitácora de desarrollo](docs/bitacora.md) ·
API interactiva en http://localhost:8000/api/docs.
