# EduMaster.ai

Plataforma empresarial de aprendizaje inteligente: gestión académica, analítica y redes neuronales con
supervisión humana. Proyecto académico grupal construido según la *Especificación funcional y técnica v1.0*
(12-11-2026), citada como **§N**.

> **Estado:** Fases 0 a 6 ✅, pruebas E2E ✅, lecciones con contenido y gestión de contraseñas ✅ ·
> pendientes: ranking aprendido y Fases 7-8.
> La hoja de ruta completa está en [docs/fase-0/backlog.md](docs/fase-0/backlog.md).

## Qué funciona hoy

| Área | Detalle |
|---|---|
| Inicio de sesión | Institución + correo + contraseña. Token de 15 min y sesión renovable con detección de robo. |
| Roles y permisos | Los 8 roles de §3. El backend valida cada petición; ocultar botones es solo comodidad. |
| Multi-institución | Cada institución ve solo sus datos. Probado con pruebas automáticas de aislamiento. |
| Bitácora | Toda acción crítica queda registrada. En PostgreSQL no se puede editar ni borrar. |
| Cursos | Catálogo con unidades y actividades, publicación, ofertas por periodo y cohorte, matrículas. |
| Lecciones | Contenido con formato, recursos y video; el docente lo edita y cada cambio sube la versión. |
| Cuentas | Cambio de contraseña, restablecimiento por la administración con cambio obligatorio. |
| Rutas de aprendizaje | Secuencias de cursos con prerrequisitos, versiones, asignación por cohorte y excepciones. |
| Aprendizaje | El estudiante marca actividades; cada evento es idempotente y recalcula su progreso. |
| Evaluaciones | Pesos que suman hasta 100 %, entregas con control de intentos y plazo, nota oficial del docente (0-20). |
| Panel | KPIs académicos reales con variación, tendencia semanal, finalización, alertas abiertas y actividad. |
| Modelo de IA | Riesgo de abandono: baselines vs. red con GRU, model card, calibración y aprobación por institución. |
| Alertas | El docente ve el riesgo de sus estudiantes con los factores que lo explican y lo marca atendido o descartado. |
| Notificaciones en vivo | Campana con contador y avisos al instante (SSE): notas, evaluaciones, certificados, alertas. |
| Analítica | 9 indicadores definidos, filtros, desglose por oferta/estudiante y exportación CSV/XLSX/PDF auditada. |
| Dominio de habilidades | Catálogo de competencias, heatmap por nivel y nivel estimado separado del validado por el docente. |
| Mapa y comunidad | Progreso por región sin exponer grupos pequeños; foros por curso con anuncios, debates y moderación. |
| Certificados | Emisión automática por criterio oficial, PDF con QR, anulación y verificación pública en `/verificar`. |
| Recomendaciones e IA Tutor | Sugerencias explicadas (siguiente actividad, entrega próxima, reforzar, retomar) con feedback y métricas de utilidad. |
| Administración | Usuarios, roles e instituciones. |
| Seguridad | Cabeceras CSP/HSTS, límites de tamaño y de peticiones por IP, modelo de amenazas y revisión OWASP (`docs/fase-7/seguridad.md`). |
| Operación | Pantalla con latencia p95, errores y conexiones en vivo frente a los objetivos; logs JSON con `correlation_id`; health checks; CI en GitHub Actions. |
| Respaldo | Respaldo cifrado (AES-256) con prueba de restauración automática; restauración con vuelta atrás. |
| Puesta en marcha | Smoke test antes de abrir el túnel, retiro del modelo (rollback), prueba de carga y runbooks (`docs/runbooks.md`). |

Los módulos que aún no existen muestran **qué incluirán y en qué fase llegan**, nunca cifras inventadas (§1).

## Instalar y abrir (Windows)

Requisitos: Python 3.13, Node 24 y Git. PostgreSQL es opcional en local (sin él se usa SQLite).

1. `instalar.bat`: instala todo, crea el `.env` con secretos aleatorios y carga las cuentas DEMO.
2. `iniciar.bat`: abre http://localhost:8000.
3. Opcional: `infra\scripts\crear_base.ps1` pasa la base a PostgreSQL.

Otros scripts: `demo.bat` (demo pública), `comprobar.bat` (smoke test) y `respaldo.bat` (respaldo cifrado y prueba de
restauración). Todos los procedimientos de operación están en [`docs/runbooks.md`](docs/runbooks.md).

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

## Actualizar una instalación existente (sin perder datos)

Con la API detenida (cierra `iniciar.bat` o `demo.bat`):

1. `respaldo.bat` (respaldo previo, §16.3).
2. `git pull` (o descarga el ZIP nuevo y cópialo encima: `.env` y `data/` se conservan).
3. `instalar.bat`: es idempotente; instala dependencias, compila la web, migra la base y completa los datos DEMO.

Las migraciones están preparadas para bases con datos (D38) y `app.seed` solo completa lo que falte (no duplica ni
borra). Luego vuelve a abrir `iniciar.bat` o `demo.bat`. Subir cambios a GitHub **no afecta** a una demo que está
corriendo: la demo sirve los archivos de tu PC, y solo cambia cuando haces los pasos anteriores y la reinicias.

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
cd apps/web && npm run build && npm run e2e              # 15 pruebas E2E (Edge en Windows, base aislada)
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
9. **Comunidad:** el docente publica un anuncio en PY-101 y a los estudiantes les llega el aviso; un estudiante
   reporta un mensaje y el docente lo oculta con motivo. **Resumen** muestra el mapa (Junín no aparece: tiene 2 personas).
10. **Rutas:** `coordinacion@andino.demo` abre «Analista de datos junior» (PY-101 → DS-201 → ML-301) y ve el avance de
    la cohorte; Valeria ve su línea de tiempo con las etapas bloqueadas hasta completar PY-101.
11. **Analítica:** el admin filtra por oferta o docente, pasa el cursor sobre un indicador para leer su definición y
    exporta a Excel; la exportación aparece en **Actividad y auditoría**. El analista solo ve agregados.
12. **Habilidades:** el docente abre el heatmap, elige PY-101 y a Valeria, revisa sus evidencias y valida «Sintaxis
    de Python»; a ella le llega el aviso y ve el nivel oficial junto al estimado.
13. **Operación:** el admin abre **Operación** mientras el público navega: latencia p95 y errores frente a los
    objetivos del documento, conexiones en vivo y frescura de los datos.
14. **Vuelta atrás:** en **Modelos de IA**, **Retirar** con un motivo; la red vuelve a «Diseño», no salen alertas
    nuevas y el retiro queda en la bitácora. Se vuelve a aprobar para seguir.

Documentación: [cómo funciona (explicación sencilla)](docs/como-funciona.md) ·
[módulos y por qué se construyeron así](docs/modulos.md) ·
PDF: [documentación del sistema](docs/pdf/EduMaster_AI_Documentacion_Sistema.pdf) y [informe de desarrollo](docs/pdf/EduMaster_AI_Informe_Desarrollo.pdf) ·
[decisiones](docs/fase-0/decisiones.md) · [bitácora de desarrollo](docs/bitacora.md) ·
[runbooks](docs/runbooks.md) · [seguridad](docs/fase-7/seguridad.md) · [acta UAT](docs/fase-7/aceptacion-uat.md) ·
API interactiva en http://localhost:8000/api/docs.
