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

## Decisiones aún abiertas (§17.1)

| Tema | Propuesta por defecto (se confirma en su fase) |
|---|---|
| Procesos oficiales vs. analíticos | Notas y certificados son oficiales; toda salida de IA es analítica. |
| Tipos de evaluación y rúbricas | Los 5 tipos de §4.6; rúbrica de 4 niveles. |
| Umbral de recomendación y revisión humana | Alertas de riesgo ≥ umbral calibrado, siempre revisadas por el docente. |
