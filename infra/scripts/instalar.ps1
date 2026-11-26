# Instalación y actualización en cualquier equipo Windows. Uso: doble clic en instalar.bat (ver docs/despliegue.md)
#   1. Comprueba Python 3.12+ (Node solo hace falta para recompilar la web).
#   2. Entorno de Python y dependencias de la API.
#   3. Web: viene compilada en el repositorio; se recompila solo con -RecompilarWeb o si falta.
#   4. Archivo .env con secretos aleatorios (si no existe) y clave de respaldos.
#   5. Migraciones de la base (seguras sobre datos existentes, D38) y cuentas DEMO (sin duplicar).
# Es idempotente: sirve para la primera instalación y para actualizar. Sin PostgreSQL usa SQLite en data/.

param([switch]$RecompilarWeb)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

Step "Comprobando requisitos"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Falta Python 3.12 o superior: https://www.python.org/downloads/ (marca 'Add python.exe to PATH')." }
$pyVersion = (& python -c "import sys;print('%d.%d' % sys.version_info[:2])").Trim()
if ([version]$pyVersion -lt [version]"3.12") { throw "Se necesita Python 3.12 o superior (hay $pyVersion)." }
Write-Host "Python $pyVersion"
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) { Write-Host "Node $(node --version)" } else { Write-Host "Node no está instalado: no hace falta, la web viene compilada." }

Step "API: entorno virtual y dependencias"
if (-not (Test-Path (Join-Path $api ".venv"))) { python -m venv (Join-Path $api ".venv") }
& (Join-Path $api ".venv\Scripts\python.exe") -m pip install -q --upgrade pip
& (Join-Path $api ".venv\Scripts\python.exe") -m pip install -q -r (Join-Path $api "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias de Python (revisa la conexion a internet)." }

# La web compilada (apps/web/dist) viene en el repositorio: sin npm se puede instalar en redes que bloquean
# registry.npmjs.org (p. ej. la del centro de estudios). Para recompilarla: npm run build (o instalar.ps1 -RecompilarWeb).
if ((Test-Path (Join-Path $web "dist\index.html")) -and -not $RecompilarWeb) {
    Step "Web: ya viene compilada (se omite npm)"
} else {
    Step "Web: dependencias y compilación"
    if (-not $node) { throw "Para recompilar la web hace falta Node 24: https://nodejs.org" }
    Push-Location $web
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Fallo npm ci (revisa la conexion a internet)." }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Fallo la compilacion de la web." }
    Pop-Location
}

$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Step "Creando .env con secretos aleatorios"
    $jwt = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
    $demo = "Demo-" + (-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 12 | ForEach-Object { [char]$_ }))
    @(
        "EDUMASTER_ENVIRONMENT=development",
        "EDUMASTER_JWT_SECRET=$jwt",
        "EDUMASTER_DEMO_PASSWORD=$demo"
    ) | Set-Content -Path $envFile -Encoding utf8
    Write-Host "Contraseña de las cuentas DEMO guardada en .env (EDUMASTER_DEMO_PASSWORD)."
}

# Clave de los respaldos cifrados (D42). Se agrega también a instalaciones anteriores que no la tenían.
if (-not (Select-String -Path $envFile -Pattern "^EDUMASTER_BACKUP_KEY=" -Quiet)) {
    $bk = & (Join-Path $api ".venv\Scripts\python.exe") -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))"
    Add-Content -Path $envFile -Value "EDUMASTER_BACKUP_KEY=$bk" -Encoding utf8
    Write-Host "Clave de respaldos agregada a .env (EDUMASTER_BACKUP_KEY). Guárdala aparte: sin ella no se restaura."
}

Step "Base de datos: migraciones y cuentas DEMO"
if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    Write-Host "AVISO: hay algo usando el puerto 8000 (¿iniciar.bat o demo.bat abiertos?). Ciérralo antes de migrar." -ForegroundColor Yellow
}
Push-Location $api
& .\.venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Fallaron las migraciones. Restaura el respaldo previo (docs/runbooks.md, runbook 5)." }
& .\.venv\Scripts\python.exe -m app.seed
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Fallo la carga de las cuentas DEMO." }
Pop-Location

Write-Host "`nListo. Ejecuta iniciar.bat (solo este equipo) o demo.bat (dirección pública)." -ForegroundColor Green
Write-Host "Contraseña de las cuentas DEMO: está en .env (EDUMASTER_DEMO_PASSWORD)." -ForegroundColor Green
