# Acta de aceptación (UAT) · release candidate

Fase 7, §13.1 y §14. Cada criterio global del documento tiene su **evidencia automática** (pruebas que corren
en cada cambio) y un **paso manual** que el grupo verifica en la demo pública. El grupo marca la última columna
el día de la prueba.

- Versión: commit de `main` publicado el día de la prueba (ver `git log -1`).
- Entorno: PC de la demo + Cloudflare Tunnel, datos DEMO.
- Pruebas automáticas al cierre de la Fase 7: **89** de API, **7** de web y **20** E2E en Playwright. La CI tiene 4 trabajos en verde.

| # | Criterio (§13.1) | Evidencia automática | Paso manual en la demo | OK |
|---|---|---|---|---|
| 22 | Todos los módulos tienen rutas, permisos, formularios, validaciones, persistencia y estados | `tests/` (API), E2E 01-06 | Recorrer el menú con admin, docente y estudiante | ☐ |
| 23 | Botones y filtros ejecutan acciones reales con confirmación o error | E2E 02-05 | Marcar una actividad, filtrar la analítica, exportar CSV | ☐ |
| 24 | Datos DEMO marcados y sustituibles sin rehacer la UI | `DemoTag`, datasheet del dataset | Ver el rótulo DEMO en el panel y en Modelos | ☐ |
| 25 | El dashboard muestra fecha y fuente de cada KPI | `test_dashboard_y_sistema.py` | Pasar el cursor sobre un KPI de "Indicadores detallados" | ☐ |
| 26 | Los eventos actualizan sin recargar y se recuperan tras reconectar | `test_notificaciones_certificados.py`, E2E "nota en vivo" | Dos navegadores: el docente publica una nota y el estudiante la ve al instante | ☐ |
| 27 | La red neuronal refleja el backend; la simulación está rotulada | `test_arquitectura_neuronal_en_estado_diseno` | Antes de aprobar: "Diseño". Al pulsar Simular: "SIMULACIÓN DEMO" | ☐ |
| 28 | El pipeline reconstruye un dataset desde su versión con el mismo esquema | Trabajo `ml` de la CI (sin fuga, huella SHA-256) | `python -m edumaster_ml.generate` (en `ml/`) y comparar la huella SHA-256 con la del datasheet | ☐ |
| 29 | El modelo publicado tiene ficha, métricas, versión, aprobación y rollback | `test_ia.py` (aprobar, retirar y volver a publicar) | Modelos de IA → Aprobar → Retirar con motivo → ver la bitácora | ☐ |
| 30 | Nadie accede a otra institución u otro estudiante | `test_permisos_y_aislamiento.py`, E2E 01 | Con admin de PACIFICO, abrir la URL de una oferta de ANDINO: responde 404 | ☐ |
| 31 | Documentación de despliegue, variables, backup, restauración y operación | `README.md`, `docs/runbooks.md` | Ejecutar `respaldo.bat` y ver "ok": true | ☐ |

## Requisitos no funcionales verificados

| Requisito | Resultado | Documento |
|---|---|---|
| Rendimiento §10.5 (escenario aula: 40 personas) | Dashboard p95 0,9 s ✅ · inferencia p95 0,25 s ✅ · lectura p95 0,51 s (límite) | `carga-aula.md` |
| Estrés (40 usuarios sin pausa) | 70 pet/s sin errores 5xx; se recupera al instante | `carga-estres.md` |
| Seguridad (OWASP, STRIDE) | 9 de 10 riesgos cubiertos; A06 con escaneo pendiente | `seguridad.md` |
| Accesibilidad | axe sin violaciones graves, teclado, móvil y movimiento reducido | E2E 01 |
| Respaldo y restauración | Cifrado, verificado por restauración de prueba (34 tablas, 1 223 filas) | `docs/runbooks.md` |

## Observaciones abiertas (no bloquean la demo)

1. Escaneo automático de dependencias en la CI (A06).
2. Lectura común en el límite del objetivo con un solo proceso. Para ampliarla: PostgreSQL, varios workers y Redis para el tiempo real (D11, D43).
3. Ranking aprendido de recomendaciones (cabeza D, §9.1): espera feedback real suficiente.

## Firmas

| Rol (§14.1) | Nombre | Fecha | Acepta |
|---|---|---|---|
| Product Owner | | | ☐ |
| Arquitectura / Backend | | | ☐ |
| Frontend / UX | | | ☐ |
| Datos / ML | | | ☐ |
| QA | | | ☐ |
