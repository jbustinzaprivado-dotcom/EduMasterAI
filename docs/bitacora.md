# Bitácora de desarrollo

Base para el informe de desarrollo y el informe mensual. Una entrada por jornada.

| Fecha | Fase | Avance |
|---|---|---|
| 2026-11-12 (jue) | — | Se propone el proyecto. Se reciben la especificación funcional y técnica y el manual de procedimientos (v1.0). |
| 2026-11-17 (mar) | 0 | Lectura y resumen de ambos documentos. Decisiones de Fase 0: multi-institución, solo adultos, dataset DEMO, primera predicción de riesgo de abandono, hosting en equipo propio con Cloudflare Tunnel, diseño según §5. Se crea el repositorio y se redactan decisiones, backlog, glosario y mapa de procesos. |
| 2026-11-17 (mar) | 1 | Fundaciones completas: API FastAPI con migraciones Alembic; login OAuth2 (token de 15 min y renovación rotatoria con detección de robo); 8 roles de §3 con permisos validados en backend; aislamiento entre instituciones; bitácora de auditoría inmutable en PostgreSQL; logs JSON con correlation_id; panel React con la paleta de §5 (KPIs reales, red neuronal en estado de diseño con simulación rotulada, actividad, hoja de ruta); administración de usuarios e instituciones; 24 pruebas de API y 3 de web; CI en GitHub Actions; scripts de instalación, inicio y demo con Cloudflare Tunnel. |
| 2026-11-19 (jue) | — | Exposición de avance (planificada). |
