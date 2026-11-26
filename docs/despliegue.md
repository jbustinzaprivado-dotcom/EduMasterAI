# Despliegue de EduMaster.ai en otro equipo

Guía paso a paso para instalar, abrir, actualizar y trasladar EduMaster.ai a cualquier PC con Windows 10 u 11.
No hace falta programar: todo se hace con doble clic en los archivos `.bat` de la carpeta del proyecto.
Los procedimientos de operación (respaldos, incidentes, monitoreo) están en [`runbooks.md`](runbooks.md).

## 1. Qué se necesita

| Programa | ¿Obligatorio? | Para qué | Cómo conseguirlo |
|---|---|---|---|
| **Python 3.12 o superior** (recomendado 3.13) | Sí | Ejecuta la plataforma | [python.org/downloads](https://www.python.org/downloads/). En el instalador marca **«Add python.exe to PATH»**. Si no tienes permisos de administrador, elige «Install just for me». |
| **Git** | Recomendado | Descargar y actualizar con un clic | [git-scm.com/download/win](https://git-scm.com/download/win). Sin Git se puede usar el ZIP (opción B). |
| **cloudflared** | Solo para la demo pública | Crear la dirección `https://…trycloudflare.com` | Con permisos: `winget install --id Cloudflare.cloudflared`. Sin permisos: ver el punto 5. |
| Node 24 | No | Solo para recompilar la web, que ya viene compilada | [nodejs.org](https://nodejs.org) |

También hace falta **internet la primera vez**, para que `instalar.bat` descargue las librerías de Python (unos 150 MB
desde pypi.org). Después, la plataforma funciona sin internet en el mismo equipo; la demo pública sí necesita conexión.

## 2. Descargar el proyecto

**Opción A, con Git (recomendada: actualizar es un clic).** Abre PowerShell en la carpeta donde lo quieras y ejecuta:

```powershell
git clone https://github.com/jbustinzaprivado-dotcom/EduMasterAI.git
```

**Opción B, con ZIP.** En GitHub: **Code → Download ZIP** y descomprímelo. Ojo: Windows crea una carpeta dentro de
otra (`EduMasterAI-main\EduMasterAI-main`). Usa la **de adentro**, la que contiene `instalar.bat`.

## 3. Instalar (primera vez)

1. Haz doble clic en **`instalar.bat`** y espera a que diga «Listo» (de 2 a 5 minutos la primera vez). Instala:
   - el entorno de Python con sus librerías;
   - el archivo `.env`, con secretos aleatorios propios de este equipo: la contraseña de las cuentas DEMO y la clave
     de los respaldos;
   - la base de datos (SQLite en `data\`) con las cuentas y los cursos DEMO.
2. **Guarda una copia de `.env` fuera del equipo**, por ejemplo en tu correo o un USB. Sin la clave
   `EDUMASTER_BACKUP_KEY` no se pueden restaurar los respaldos.
3. Para ver la contraseña de las cuentas DEMO, abre `.env` con el Bloc de notas y busca `EDUMASTER_DEMO_PASSWORD`.
   Cada instalación tiene la suya.

`instalar.bat` se puede ejecutar las veces que quieras: no borra datos ni duplica cuentas.

## 4. Abrir la plataforma

| Quiero… | Haz doble clic en | Resultado |
|---|---|---|
| Usarla solo en este equipo | `iniciar.bat` | Se abre http://localhost:8000 |
| Mostrarla a otras personas por internet | `demo.bat` | Prueba que todo funcione (smoke test) y muestra una dirección `https://…trycloudflare.com` |
| Comprobar que responde bien | `comprobar.bat` (con la plataforma abierta) | Debe decir «Todo en orden» |

- Solo puede estar abierto uno de los dos a la vez (`iniciar.bat` o `demo.bat`), porque ambos usan el puerto 8000.
- La dirección de `demo.bat` cambia cada vez que se abre y funciona mientras su ventana siga abierta. Para cerrar:
  **Ctrl+C**.

**Cuentas DEMO** (institución · correo): `ANDINO` · `admin@andino.demo` (administración), `docente@andino.demo`,
`estudiante@andino.demo`, `coordinacion@andino.demo`, `analista@andino.demo`, `ml@andino.demo`,
`auditoria@andino.demo`; `PLATAFORMA` · `superadmin@edumaster.demo`. Todas usan la contraseña del `.env`.

**Antes de una presentación** (la base nueva empieza sin modelo publicado):
1. Como `admin@andino.demo`: **Modelos de IA → Aprobar publicación**.
2. Como `docente@andino.demo`: **Cursos → PY-101 → Estudiantes y riesgo → Actualizar riesgo con IA**.
3. El guion completo de la demo está en el [README](../README.md#guion-de-la-demo-de-ia).

## 5. Equipos sin permisos de administrador o con red restringida

Probado en la PC del centro de estudios: sin administrador y con npm bloqueado.

- **Python:** el instalador oficial permite «Install just for me», que no pide administrador.
- **npm bloqueado:** no importa; la web viene compilada en el repositorio (D49).
- **cloudflared sin instalar:** descarga `cloudflared-windows-amd64.exe` desde
  [github.com/cloudflare/cloudflared/releases](https://github.com/cloudflare/cloudflared/releases), renómbralo a
  **`cloudflared.exe`** y déjalo en la carpeta del proyecto (junto a `demo.bat`) o en una subcarpeta `tools\`.
  `demo.bat` lo encuentra solo. Ese archivo no se sube a Git.
- **pip bloqueado** (no descarga librerías): pide en la red que habiliten `pypi.org` y `files.pythonhosted.org`, o
  instala desde un equipo con internet y copia la carpeta completa, incluida `apps\api\.venv`, a una ruta igual
  (el entorno de Python guarda rutas absolutas).
- **Windows bloquea el `.bat`** («Windows protegió su PC»): **Más información → Ejecutar de todas formas**. Pasa con
  archivos descargados de internet.

## 6. Actualizar a una versión nueva

Con `iniciar.bat` y `demo.bat` cerrados, haz doble clic en **`actualizar.bat`**. En un solo paso:

1. Comprueba que la plataforma esté detenida.
2. Hace un **respaldo cifrado** de la base y lo verifica. Si falla, no sigue.
3. Descarga la versión nueva (`git pull`; nunca borra cambios locales).
4. Ejecuta `instalar.bat`: librerías nuevas, **migraciones de la base** sin perder datos (D38) y datos DEMO que falten.

Si instalaste con ZIP: descarga el ZIP nuevo, cópialo encima de la carpeta (`.env` y `data\` se conservan) y ejecuta
`instalar.bat`. Después de actualizar, recarga el navegador con **Ctrl+F5**.

Si algo sale mal, la base anterior se recupera con el respaldo del paso 2 (runbook 5 de [`runbooks.md`](runbooks.md)).

## 7. Llevar los datos de un equipo a otro

La instalación nueva empieza con los datos DEMO. Para conservar lo que ya se hizo en otro equipo (notas, alertas,
certificados, publicaciones):

**Opción 1, copiar la carpeta de datos** (la más simple):
1. En el equipo de origen, cierra la plataforma.
2. Copia `.env` y la carpeta `data\` al equipo nuevo, en la carpeta del proyecto (reemplaza los que haya).
3. En el equipo nuevo, ejecuta `instalar.bat`: aplica las migraciones si la base es de una versión anterior.

**Opción 2, con un respaldo cifrado:**
1. En el equipo de origen: `respaldo.bat`. Copia el archivo `backups\edumaster-….emb` y el `.env`.
2. En el equipo nuevo: deja el `.env` copiado en la carpeta del proyecto (la clave `EDUMASTER_BACKUP_KEY` debe ser
   la misma) y restaura desde PowerShell:

```powershell
cd apps\api; .\.venv\Scripts\python.exe -m app.backup restaurar ..\..\backups\edumaster-AAAAMMDD-HHMMSS.emb; .\.venv\Scripts\alembic.exe upgrade head
```

Las contraseñas de las cuentas viajan con la base: tras trasladar los datos, las cuentas DEMO usan la contraseña del
`.env` de origen.

## 8. Problemas frecuentes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| «El sistema no puede encontrar la ruta especificada» al abrir `iniciar.bat` | Esa carpeta no se instaló (suele pasar con el ZIP) | Ejecuta `instalar.bat` en esa misma carpeta. |
| «Institución, correo o contraseña incorrectos» | Se usa la contraseña de otra instalación | Usa `EDUMASTER_DEMO_PASSWORD` del `.env` de la carpeta que abriste. |
| «El puerto 8000 está en uso» | `iniciar.bat` o `demo.bat` ya están abiertos | Ciérralos y vuelve a intentar. |
| La web se ve antigua o falta una sección | Caché del navegador | **Ctrl+F5**. |
| Falla una página nueva después de actualizar | El servidor sigue con la versión anterior en memoria | Cierra `iniciar.bat`/`demo.bat`, ejecuta `actualizar.bat` y vuelve a abrir. |
| «Falta cloudflared» | No está instalado ni en la carpeta | Punto 5: `cloudflared.exe` portable. |
| «Fallaron las migraciones» | La base está abierta o dañada | Cierra la plataforma y repite; si persiste, restaura el respaldo previo. |
| Red neuronal en «Diseño» y sin alertas | No hay modelo aprobado en esta base | Punto 4: aprobar publicación. |

Más incidentes y su solución en [`runbooks.md`](runbooks.md#7-incidentes-frecuentes).

## 9. Qué hace cada archivo

| Archivo | Qué hace |
|---|---|
| `instalar.bat` | Instala o repara: librerías, `.env`, migraciones y datos DEMO. Idempotente. |
| `actualizar.bat` | Respaldo + descarga de la versión nueva + `instalar.bat`. |
| `iniciar.bat` | Abre la plataforma en este equipo (http://localhost:8000). |
| `demo.bat` | Abre la plataforma con dirección pública (Cloudflare Tunnel) tras un smoke test. |
| `comprobar.bat` | Smoke test de una plataforma en marcha (`comprobar.bat https://…` para la pública). |
| `respaldo.bat` | Respaldo cifrado de la base, verificado al crearlo. |
| `infra\scripts\crear_base.ps1` | Opcional: pasar de SQLite a PostgreSQL. |
