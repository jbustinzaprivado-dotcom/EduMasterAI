# Registro de decisiones (Fase 0)

Documento rector: `Documentacion_EduMaster_AI_Enterprise` v1.0 (12-11-2026), citado como **§N**.
Cuando una decisión completa algo que el documento deja abierto, se indica la sección.

| ID | Decisión | Fuente / motivo |
|---|---|---|
| D01 | Repositorio nuevo `EduMasterAI`, monorepo con `apps/web`, `apps/api`, `ml`, `infra`, `docs`. | §15.1 |
| D02 | Proyecto académico grupal. No es producción real, pero cada pantalla debe **demostrar que funciona** con datos conectados. | Decisión de alcance (pág. 2) |
| D03 | Hosting: equipo propio + **Cloudflare Tunnel**. Una sola puerta pública: la API sirve también la web compilada (sin CORS). | §17.1 deja abierta la nube/servidor |
| D04 | **Multi-institución** desde el inicio: `organization_id` en todas las entidades y filtrado obligatorio en backend, con pruebas de aislamiento. Row Level Security se evalúa en la Fase 7. | §17.1, §7.2, §11 |
| D05 | Población: **solo adultos**. Privacidad estándar según la Ley N.° 29733; sin flujo de apoderados. | §17.1, §11 |
| D06 | Dataset **sintético rotulado DEMO**; nunca se presenta como real. | §8.1 |
| D07 | Primera predicción: **riesgo de abandono** (cabeza C de §9.1), siempre como alerta de apoyo con revisión humana. | §17.1, §9.5 |
| D08 | Autenticación **OAuth2 propia de la API**: token de acceso JWT de 15 min y token de renovación rotatorio en cookie `httpOnly`, con detección de reutilización. Sin Keycloak, para tener un solo túnel y una explicación sencilla; migrable a OIDC institucional. | §10.1 admite OIDC/OAuth2 |
| D09 | Inicio de sesión con **código de institución + correo + contraseña**, porque el correo es único por institución. El superadministrador pertenece a la institución de plataforma `PLATAFORMA`. | §7.3 |
| D10 | Sin captura de referencia: la interfaz sigue la paleta y composición de **§5**. Sistema de componentes propio sobre Tailwind. | §5, §6.1 ("o sistema propio") |
| D11 | Redis + cola de trabajos se introducen cuando existan trabajos largos (Fases 3-5). En Windows se decidirá entre Memurai, WSL o cola en PostgreSQL. | §6.1 (RECOMENDADO) |
| D12 | Python 3.13 (cumple "3.12+"), React 19 + TypeScript estricto + Vite. | §6.1 |
| D13 | Pruebas rápidas en SQLite en memoria; la CI las repite contra **PostgreSQL** y valida migraciones. | §13 |
| D14 | Paneles sin datos todavía muestran **en qué fase se construyen**, nunca cifras inventadas. La red neuronal se muestra como diseño y su animación solo como "SIMULACIÓN DEMO". | §1, §5.4, §13.1 |
| D15 | La **cohorte** se modela como el grupo de cada oferta de curso (campo `cohort`), no como entidad aparte. Suficiente para asignar y filtrar; se separa si un grupo cursa varias ofertas juntas. | §7.1 |
| D16 | La historia DEMO (6-9 semanas de eventos, entregas y notas) se genera con **perfiles sintéticos** (45 % constante, 35 % irregular, 20 % en riesgo), semilla fija y rótulo `demo`. | §8.1 |
| D17 | Gráficos con **SVG propio** (tendencia y dona) en lugar de ECharts/Recharts: menos peso para la demo por túnel. Tienen leyenda, unidades, tooltip y estados vacío/carga/error. | §6.1 (RECOMENDADO), §5.2 |
| D18 | Escala de notas **vigesimal (0-20)** por defecto, la usual en Perú; cuenta el mejor intento calificado y el promedio se pondera por peso. | §4.6 ("reglas configurables") |
| D19 | **Rutas de aprendizaje (§4.2) pospuestas**: la Fase 2 entrega cursos, ofertas, matrículas, evaluaciones y eventos; las rutas se suman después porque no bloquean al modelo. | §14.1 (orden) |
| D20 | Registro de modelos en archivos (`ml/registry`: pesos + model card) y en la base (`model_versions`). MLflow y DVC quedan pospuestos: el dataset se reconstruye exacto con la semilla y su huella SHA-256. | §6.1 (RECOMENDADO), §9.6 |
| D21 | Los pesos del modelo (~90 KB) se versionan en Git para que la demo funcione sin PyTorch; los datasets no se suben, solo su ficha (datasheet). | §15.2 (prohíbe archivos grandes) |
| D22 | El **estudiante no ve su puntaje de riesgo** (evita etiquetarlo). Lo ven el docente de la oferta, la administración y la auditoría; el analista solo agregados. | §3, §9.8 |
| D23 | La publicación de un modelo se aprueba **por institución** (`model_deployments`) y la hace su administrador. El ML Engineer registra y ejecuta, pero no aprueba. | §3, §9.6 pasos 17-19 |
| D24 | La API predice con **NumPy** usando los pesos exportados (sin PyTorch en el servidor). Una prueba verifica que da lo mismo que PyTorch. | §9.4 "inferencia en servicio separado" |
| D25 | Probabilidades **calibradas** con Platt en validación. El umbral de alerta se elige en validación: mejor F1 con recall ≥ 0,6. | §9.4, §9.5 |
| D26 | Regla de publicación: la red se publica solo si supera al baseline logístico en PR-AUC de validación (≥ 0,005) sin empeorar el Brier; si no, se publica el baseline. | §9.1 "Importante" |
| D27 | Recomendaciones con un **motor de reglas explicable** (`reglas-v1`): siguiente actividad, entrega próxima, reforzar tras nota baja y retomar tras inactividad. El modelo de riesgo solo sube la prioridad de «retomar» (sin mostrar el puntaje, D22). La cabeza D de §9.1 (ranking aprendido) se entrenará con el feedback que este motor recoge. | §4.5, §4.11, §9.1 |

## Decisiones aún abiertas (§17.1)

| Tema | Propuesta por defecto (se confirma en su fase) |
|---|---|
| Procesos oficiales vs. analíticos | Notas y certificados son oficiales; toda salida de IA es analítica. |
| Tipos de evaluación y rúbricas | Los 5 tipos de §4.6; rúbrica de 4 niveles. |
| Umbral de recomendación y revisión humana | Resuelto en D25: alerta "alta" si la probabilidad calibrada supera el umbral; el docente la marca atendida o la descarta con motivo. |
