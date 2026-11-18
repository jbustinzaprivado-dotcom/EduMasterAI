# Backlog del producto (Fase 0)

Priorizado por valor y riesgo, en el orden obligatorio del manual (§14.1). Cada épica cierra con la
"puerta de salida" de su fase (§14). Estado: ✅ hecho · 🔄 en curso · ⏳ pendiente.

## Fase 0 · Descubrimiento
- ✅ Registro de decisiones, glosario y mapa de procesos (`docs/fase-0`).
- ✅ Backlog priorizado y criterios de aceptación.

## Fase 1 · Fundaciones ✅ (17-11-2026)
| ID | Historia de usuario | Criterio de aceptación |
|---|---|---|
| F1-01 | Como usuario, inicio sesión con mi institución, correo y contraseña. | Credenciales erróneas → mensaje genérico; éxito → token de 15 min y sesión renovable. |
| F1-02 | Como usuario, mi sesión se renueva sin volver a escribir la contraseña. | Token de renovación rotatorio; reutilizar uno viejo revoca toda la sesión. |
| F1-03 | Como administrador, gestiono usuarios y roles **solo de mi institución**. | Otra institución → 404; acción auditada. |
| F1-04 | Como superadministrador, veo y creo instituciones. | Solo el rol con `org.manage`. |
| F1-05 | Como auditor, consulto la bitácora sin poder modificarla. | Solo lectura; PostgreSQL bloquea UPDATE/DELETE. |
| F1-06 | Como cualquier rol, veo el panel con KPIs reales de lo que ya existe y el estado del resto. | Cada KPI muestra valor, fuente y fecha. |
| F1-07 | Como equipo, cada cambio pasa pruebas y migraciones en la CI. | GitHub Actions en verde. |
| F1-08 | Como operador, cada error y log lleva un `correlation_id`. | Errores con `code`, `message`, `details`, `correlation_id`. |

## Fase 2 · Core académico ✅ (17-11-2026, salvo rutas)
| ID | Historia de usuario | Estado |
|---|---|---|
| F2-01 | Como administrador, creo cursos con unidades y actividades y los publico. | ✅ |
| F2-02 | Como administrador, abro ofertas (periodo, docente, cohorte) y matriculo estudiantes. | ✅ |
| F2-03 | Como estudiante, veo mis cursos y marco actividades; mi progreso se recalcula. | ✅ |
| F2-04 | Como sistema, recibo eventos idempotentes (`event_id`) y rechazo los inválidos. | ✅ |
| F2-05 | Como docente, creo evaluaciones (pesos ≤ 100 %), recibo entregas y registro la nota oficial. | ✅ |
| F2-06 | Como docente, veo a mis estudiantes con progreso, última actividad y nota ponderada. | ✅ |
| F2-07 | Como coordinador, creo rutas de aprendizaje. | ⏳ pospuesta (D19) |

## Fase 3 · Dashboard y tiempo real (🔄)
- ✅ KPIs académicos con variación (activos 7 días, horas 30 días, finalización, matrículas).
- ✅ Tendencia semanal y finalización de cursos.
- ⏳ Mapa agregado, certificados y notificaciones por WebSocket/SSE.

## Fase 4 · Dataset y analítica (⏳)
Generador DEMO, pipeline de 10 pasos de §8.4, split temporal, datasheet y reportes exportables.

## Fase 5 · Modelo neuronal (⏳)
Baselines (regresión logística, boosting) y la red de §9.1 empezando por **riesgo de abandono**;
MLflow y model card.

## Fase 6 · IA en producto (⏳)
Servicio de inferencia, recomendaciones explicadas, feedback y visualizador neuronal con estados reales.

## Fase 7 · Endurecimiento (⏳)
Seguridad (OWASP, rate limits), accesibilidad, carga, respaldo y restauración.

## Fase 8 · Puesta en marcha de la demostración (⏳)
Túnel de Cloudflare, runbook y guion de exposición.
