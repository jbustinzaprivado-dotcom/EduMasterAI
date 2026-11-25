# Runbooks de operación (Fase 8)

Procedimientos paso a paso para el PC que hospeda la demo (D03). Cada uno dice **cuándo usarlo**, **qué hacer** y
**cómo comprobar** que salió bien. Todos los `.bat` están en la raíz del proyecto.

| Situación | Runbook |
|---|---|
| Instalar en un equipo nuevo | [1](#1-instalación) |
| Abrir la demo pública | [2](#2-arranque-de-la-demo-pública) |
| Llevar a la demo una versión nueva de GitHub | [3](#3-actualización-con-respaldo-previo) |
| Hacer y probar un respaldo | [4](#4-respaldo-y-prueba-de-restauración) |
| Recuperar la base | [5](#5-restauración) |
| Un modelo da malas alertas | [6](#6-vuelta-atrás-del-modelo-rollback) |
| Algo no funciona durante la demo | [7](#7-incidentes-frecuentes) |
| Vigilar la salud de la plataforma | [8](#8-monitoreo) |

**Objetivos de continuidad (§16.4):**
- **RPO de 24 horas:** se pierde como máximo un día de datos, gracias al respaldo diario.
- **RTO de 4 horas:** la restauración real tarda minutos; ver el runbook 5.

## 1. Instalación

1. Instala Python 3.13, Node 24 y Git. Para la demo pública, instala también `cloudflared`:
   ```bash
   winget install --id Cloudflare.cloudflared
   ```
2. Clona el repositorio con git (no descargues el ZIP, así las actualizaciones son un `git pull`):
   ```bash
   git clone https://github.com/jbustinzaprivado-dotcom/EduMasterAI.git
   ```
3. Haz doble clic en `instalar.bat`. Crea `.env` con secretos aleatorios, la contraseña DEMO y la clave de respaldos.
4. **Guarda una copia de `.env` fuera del PC.** Sin `EDUMASTER_BACKUP_KEY` no se pueden restaurar los respaldos.

**Cómo comprobar:** abre `iniciar.bat` y, en otra ventana, ejecuta `comprobar.bat`. Debe decir "Todo en orden."

## 2. Arranque de la demo pública

1. Cierra `iniciar.bat` si está abierto, porque el puerto 8000 tiene que estar libre.
2. Haz doble clic en `demo.bat`. Arranca la API en modo demo, ejecuta el smoke test y abre el túnel.
3. Copia la dirección `https://…trycloudflare.com` que aparece en la ventana. Cambia cada vez que se abre el túnel.
4. Entra con `admin@andino.demo` y la contraseña `EDUMASTER_DEMO_PASSWORD` del `.env`.

**Cómo comprobar:** el smoke test aparece en verde antes de que se abra el túnel. Para revisarlo desde otro equipo:
```bash
comprobar.bat https://xxxx.trycloudflare.com
```

Para terminar, pulsa Ctrl+C en la ventana. Se cierran el túnel y la API.

## 3. Actualización con respaldo previo

Sigue el §16.3: primero respaldo, después migraciones compatibles, y al final smoke test.

1. Detén `demo.bat` o `iniciar.bat`.
2. Ejecuta `respaldo.bat` y comprueba que diga `"ok": true`.
3. Actualiza el código:
   ```bash
   git pull
   ```
   Si instalaste desde un ZIP, descarga el ZIP nuevo y cópialo encima. `.env` y `data/` se conservan.
4. Ejecuta `instalar.bat`. Es idempotente: instala dependencias, compila la web, migra la base y completa los datos DEMO sin borrar nada.
5. Abre `demo.bat`. El smoke test debe salir en verde.

Si algo falla, vuelve a la versión anterior: `git checkout <commit anterior>`, después `instalar.bat`, y restaura el respaldo del paso 2 (runbook 5).

## 4. Respaldo y prueba de restauración

**Respaldo manual:** haz doble clic en `respaldo.bat`. El script:
1. Crea `backups/edumaster-AAAAMMDD-HHMMSS.emb`, cifrado con AES-256-GCM, junto con un manifiesto `.json`. El manifiesto guarda la revisión de la base, el SHA-256 y las filas por tabla.
2. Lo restaura en una base temporal y compara las filas tabla por tabla. Debe responder `"ok": true`.

Un respaldo que no se ha probado no se considera un respaldo (§16.4). Por eso cada copia se prueba al crearla.

**Respaldo diario automático (RPO 24 h):** ejecuta esta orden una sola vez en PowerShell, cambiando la ruta por la de tu instalación:
```powershell
schtasks /Create /SC DAILY /ST 23:00 /TN "EduMaster respaldo" /TR "cmd /c cd /d C:\ruta\EduMasterAI\apps\api && .venv\Scripts\python.exe -m app.backup crear"
```

**Copia externa:** copia la carpeta `backups/` a otro disco o a la nube. Los archivos están cifrados, así que se pueden guardar fuera del PC.

**Otros comandos útiles (desde `apps/api`):**
- Ver los respaldos guardados:
  ```bash
  .venv/Scripts/python -m app.backup listar
  ```
- Probar un respaldo concreto:
  ```bash
  .venv/Scripts/python -m app.backup verificar ../../backups/<archivo>.emb
  ```

## 5. Restauración

1. Detén la API (`demo.bat` o `iniciar.bat`).
2. Restaura el respaldo desde `apps/api`:
   ```bash
   .venv/Scripts/python -m app.backup restaurar ../../backups/<archivo>.emb
   ```
   Antes de reemplazar la base, guarda la actual en `backups/antes-de-restaurar/`, para poder deshacerlo.
3. Aplica las migraciones, por si el respaldo es de una versión anterior:
   ```bash
   .venv/Scripts/alembic upgrade head
   ```
4. Abre `iniciar.bat` y ejecuta `comprobar.bat`.

Si el respaldo no se puede descifrar, revisa que `EDUMASTER_BACKUP_KEY` en `.env` sea la misma que se usó al crearlo. Si el SHA-256 no coincide, el archivo está dañado: usa otro.

**Con PostgreSQL:** el mismo comando usa `pg_dump` y `pg_restore`, que deben estar en el PATH.

## 6. Vuelta atrás del modelo (rollback)

**Cuándo usarlo:** las alertas no tienen sentido, las métricas caen o hay una queja fundada (§9.8, §16.3 paso 38).

1. Entra con un rol que tenga `ml.approve` (administración).
2. Ve a **Modelos de IA**, pulsa **Retirar** en la versión publicada y escribe el motivo, que es obligatorio.
3. Desde ese momento, la institución no genera alertas nuevas. Las predicciones anteriores quedan como historial y la red vuelve al estado "Diseño".
4. Para volver a publicar, aprueba otra versión, o la misma si el problema era de datos.

**Cómo comprobar:** en **Actividad y auditoría** aparece `model.retired` con el motivo, y el personal recibe una notificación.

## 7. Incidentes frecuentes

| Síntoma | Causa probable | Acción |
|---|---|---|
| `demo.bat`: "El puerto 8000 está en uso" | `iniciar.bat` sigue abierto | Ciérralo y vuelve a abrir `demo.bat`. |
| No se puede entrar: "Institución, correo o contraseña incorrectos" | La contraseña es de otra instalación | Usa la `EDUMASTER_DEMO_PASSWORD` del `.env` de **esa** carpeta. |
| "Demasiados intentos" al iniciar sesión | Más de 10 intentos por minuto a la misma cuenta, o más de 60 desde una IP (D46) | Espera 1 minuto. Si más de 60 personas entran a la vez desde el mismo Wi-Fi, sube `EDUMASTER_LOGIN_RATE_LIMIT` en `.env` (el tope por IP es 6 veces ese valor). |
| Respuesta 429 "Demasiadas peticiones" | Más de 600 peticiones por minuto de una misma persona, o más de 6 000 desde una IP (D49) | Sube `EDUMASTER_API_RATE_LIMIT` en `.env` y reinicia (el tope por IP es 10 veces ese valor). |
| La dirección pública no carga | Se cerró el túnel o cambió la URL | Revisa la ventana de `demo.bat` y comparte la URL nueva. |
| Las notificaciones no llegan en vivo | El navegador perdió la conexión | Se reconecta solo y recupera lo perdido. Si no, recarga la página (F5). |
| La web va lenta | Demasiados usuarios para un solo proceso | Mira **Operación**: si el p95 pasa del objetivo, limita la demo a unas 40 personas a la vez (D43). |
| La web muestra una versión vieja | Caché del navegador | Pulsa Ctrl+F5. |
| La API no arranca en modo demo | Falta un secreto o la cookie no es segura | Lee el mensaje: `EDUMASTER_JWT_SECRET` debe tener al menos 32 caracteres. `demo.bat` ya fija la cookie segura. |

Todos los errores incluyen un `correlation_id`. Búscalo en la ventana de la API para ver qué pasó.

## 8. Monitoreo

- **Pantalla Operación** (administración, auditoría y ML): latencia p50/p95/p99 por ruta, errores 5xx, peticiones por minuto, conexiones en vivo, último evento de aprendizaje y predicciones de los últimos 7 días, comparados con los objetivos del §10.5. Se actualiza cada 10 s.
- **Health checks:** `/api/v1/health` indica si la API está viva y `/api/v1/health/ready` si la base responde.
- **Logs:** la ventana de la API muestra una línea JSON por petición, con su `correlation_id` y duración.
- **Capacidad medida:** ver `docs/fase-7/carga-aula.md` y `carga-estres.md`.

## Variables de entorno (`.env`)

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `EDUMASTER_ENVIRONMENT` | `development`, `test` o `demo` | `development` (`demo.bat` pone `demo`) |
| `EDUMASTER_DATABASE_URL` | Conexión a la base | SQLite en `data/` |
| `EDUMASTER_JWT_SECRET` | Firma de los tokens; al menos 32 caracteres en demo | La genera `instalar` |
| `EDUMASTER_DEMO_PASSWORD` | Contraseña de las cuentas DEMO | La genera `instalar` |
| `EDUMASTER_BACKUP_KEY` | Clave AES-256 de los respaldos | La genera `instalar` |
| `EDUMASTER_LOGIN_RATE_LIMIT` | Intentos de inicio de sesión por minuto por cuenta (por IP: ×6) | 10 |
| `EDUMASTER_API_RATE_LIMIT` | Peticiones por minuto por persona (por IP: ×10) | 600 |
| `EDUMASTER_MAX_BODY_BYTES` | Tamaño máximo de una petición | 2 000 000 |
| `EDUMASTER_COOKIE_SECURE` | Cookie solo por HTTPS | `false` (`demo.bat` pone `true`) |
| `EDUMASTER_TRUST_CLOUDFLARE_IP` | Usar la IP real que envía Cloudflare | `false` (`demo.bat` pone `true`) |
