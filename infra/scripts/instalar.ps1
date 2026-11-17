# Primera instalación en un equipo del grupo (Windows). Uso: doble clic en instalar.bat
#   1. Entorno de Python e dependencias de la API.
#   2. Dependencias de la web y compilación.
#   3. Archivo .env con secretos aleatorios (si no existe).
#   4. Migraciones de la base y cuentas DEMO.
# Sin PostgreSQL configurado usa SQLite en data/ (suficiente para probar). Para PostgreSQL: crear_base.ps1.

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

Step "Web: dependencias y compilación"
Push-Location $web
npm ci
npm run build
Pop-Location

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

Step "Base de datos: migraciones y cuentas DEMO"
Push-Location $api
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.seed
Pop-Location

Write-Host "`nListo. Ejecuta iniciar.bat para abrir EduMaster.ai." -ForegroundColor Green
