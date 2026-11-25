# Seguridad: modelo de amenazas y revisión OWASP (Fase 7)

Alcance: la demostración pública (PC del equipo + Cloudflare Tunnel, D03) con datos sintéticos DEMO. Cada control
indica **dónde está** y **qué prueba lo demuestra**, para poder enseñarlo en la exposición.

## 1. Qué se protege y de quién

| Activo | Por qué importa |
|---|---|
| Datos de estudiantes (notas, progreso, riesgo) | Ley 29733; una predicción de riesgo expuesta estigmatiza (§9.8). |
| Cuentas y sesiones | Con una sesión robada se actúa como docente o administrador. |
| Separación entre instituciones | Una institución nunca debe ver a otra (multi-tenant, §3). |
| Bitácora de auditoría | Es la prueba de quién hizo qué; si se altera, no hay control. |
| Modelo publicado | Un modelo malo genera alertas falsas a docentes. |
| Respaldos | Contienen toda la base. |

Adversarios: visitante anónimo por Internet (el túnel es público), usuario legítimo que intenta ver más de lo que
le corresponde (otro estudiante, otra institución) y bots de fuerza bruta.

## 2. Modelo de amenazas (STRIDE)

| Amenaza | Ejemplo | Control | Evidencia |
|---|---|---|---|
| **S**uplantación | Adivinar contraseñas | PBKDF2-SHA256 600 000 iteraciones, mensaje genérico, 10 intentos/min por IP y correo y 60 por IP (D46), política de contraseñas (D37) | `test_auth.py`, `test_lecciones_contrasenas.py` |
| **S**uplantación | Robar el token de renovación | Cookie httpOnly + Secure + SameSite=Strict, rotación y detección de reutilización (revoca la sesión) | `test_auth.py` |
| **T**ampering | Alterar la bitácora | Sin endpoints de UPDATE/DELETE; en PostgreSQL un trigger los bloquea | trigger en la migración 0001 (la CI corre sobre PostgreSQL) |
| **T**ampering | Alterar un respaldo | AES-256-GCM autenticado + SHA-256 en el manifiesto (D42) | `test_respaldo.py` |
| **R**epudio | "Yo no aprobé ese modelo" | Bitácora con actor, IP real (CF-Connecting-IP), correlation_id | `test_ia.py` |
| **I**nformation disclosure | Ver otra institución | Filtro por `organization_id` en cada consulta; otra institución → 404 (no revela que existe) | `test_permisos_y_aislamiento.py`, E2E 01 |
| **I**nformation disclosure | Estudiante que ve a otro | ABAC por matrícula y oferta (`offerings_query`) | `test_academico.py` |
| **I**nformation disclosure | Reidentificar en el mapa | k-anonimato k=3 por región (D30) | `test_mapa_comunidad.py` |
| **D**enegación de servicio | Inundar la API | 600 pet/min por persona y 6 000 por IP, cuerpo ≤ 2 MB, pool de conexiones alineado y espera máxima de 10 s (D40, D43, D49) | `test_endurecimiento.py`, prueba de carga |
| **E**levación de privilegios | Docente que se asigna "admin" | RBAC por permisos en la API (la web solo oculta); roles globales solo por superadmin | `test_permisos_y_aislamiento.py` |
| **E**levación de privilegios | ML Engineer que publica su modelo | Separación de funciones: `ml.manage` registra, `ml.approve` publica/retira | `test_ia.py` |

## 3. OWASP Top 10 (2021)

| Riesgo | Estado | Cómo se cubre |
|---|---|---|
| A01 Control de acceso roto | ✅ | `require()` por permiso en cada endpoint, ABAC por oferta, 404 entre instituciones, pruebas de aislamiento horizontal y vertical. |
| A02 Fallas criptográficas | ✅ | HTTPS por Cloudflare + HSTS, PBKDF2 600k, JWT HS256 con secreto ≥ 32 caracteres obligatorio en demo, respaldos AES-256-GCM. |
| A03 Inyección | ✅ | SQLAlchemy con parámetros (sin SQL concatenado con datos), validación Pydantic, React escapa todo el texto (no hay `innerHTML`), CSP `script-src 'self'`. |
| A04 Diseño inseguro | ✅ | Este modelo de amenazas, revisión humana de alertas (§9.8), aprobación de modelos, datos DEMO rotulados. |
| A05 Configuración incorrecta | ✅ | La API no arranca en demo con secretos por defecto ni cookie insegura; cabeceras de seguridad; `/api/docs` es el único sin CSP estricta. |
| A06 Componentes vulnerables | ⚠️ | Versiones fijadas en `requirements.txt` y `package-lock.json`. Pendiente: escaneo automático (`pip-audit`, `npm audit`) en la CI. |
| A07 Identificación y autenticación | ✅ | Límite de intentos, mensaje genérico, sesión de 15 min renovable, cambio de contraseña obligatorio tras restablecer. |
| A08 Integridad de software y datos | ✅ | Eventos idempotentes con `event_id`, modelos con SHA-256 del dataset, respaldos autenticados, CI obligatoria. |
| A09 Registro y monitoreo | ✅ | Logs JSON con correlation_id, bitácora inmutable, pantalla de Operación con p95 y errores 5xx (D41). |
| A10 SSRF | ✅ | El servidor no descarga URLs. Los enlaces de lecciones solo aceptan http/https y los abre el navegador. |

Otros puntos de §11:
- **CSRF:** el token de acceso viaja en una cabecera (no en una cookie). La cookie de renovación es SameSite=Strict y solo vale en `/api/v1/auth`.
- **Subida de archivos y antivirus:** la versión actual no recibe archivos. Los recursos son enlaces. Si se agregan archivos: límite de tamaño, tipo por contenido, antivirus y URLs firmadas que expiran.
- **Row Level Security (D45):** el §11 la plantea como frontera *adicional* si se elige PostgreSQL. La separación ya se hace en la aplicación y está probada. Activar RLS es el siguiente paso cuando haya instituciones reales.
- **Ley 29733:** solo personas adultas (D05) y datos sintéticos. Con datos reales se necesita asesoría legal (§11).

## 4. Riesgos aceptados para la demostración

| Riesgo | Por qué se acepta | Mitigación |
|---|---|---|
| Una sola instancia y SQLite | Es una demo en un PC | Capacidad medida (D43). PostgreSQL y Redis están documentados (D11). |
| URL del túnel temporal | No hay dominio propio | Túnel con nombre si se compra un dominio (runbook §7). |
| Contraseña DEMO común | Cuentas de demostración | Está en `.env`, distinta en cada instalación, y se puede cambiar desde el perfil. |
