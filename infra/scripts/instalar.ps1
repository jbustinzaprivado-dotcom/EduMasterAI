# Primera instalación en un equipo del grupo (Windows). Uso: doble clic en instalar.bat
#   1. Entorno de Python e dependencias de la API.
#   2. Dependencias de la web y compilación.
#   3. Archivo .env con secretos aleatorios (si no existe).
#   4. Migraciones de la base y cuentas DEMO.
# Sin PostgreSQL configurado usa SQLite en data/ (suficiente para probar). Para PostgreSQL: crear_base.ps1.

param([switch]$RecompilarWeb)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

Step "Comprobando Python y Node"
python --version
node --version

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
Push-Location $api
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.seed
Pop-Location

Write-Host "`nListo. Ejecuta iniciar.bat para abrir EduMaster.ai." -ForegroundColor Green
