# Actualiza una instalación a la última versión de GitHub sin perder datos (runbook 3, §16.3).
# Uso: doble clic en actualizar.bat, con iniciar.bat y demo.bat cerrados.
#   1. Comprueba que la plataforma esté detenida (puerto 8000 libre).
#   2. Respaldo cifrado de la base, verificado (D42). Si falla, no sigue.
#   3. git pull (solo avance rápido: nunca mezcla ni borra cambios locales).
#   4. instalar.ps1: dependencias, migraciones seguras (D38) y datos DEMO que falten.

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$api = Join-Path $root "apps\api"
$python = Join-Path $api ".venv\Scripts\python.exe"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    throw "EduMaster.ai sigue abierto (puerto 8000). Cierra iniciar.bat o demo.bat y vuelve a ejecutar actualizar.bat."
}

if (Test-Path $python) {
    Step "Respaldo previo de la base (se puede restaurar si algo sale mal)"
    Push-Location $api
    & $python -m app.backup crear
    $ok = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $ok) { throw "El respaldo falló: no se actualiza. Revisa EDUMASTER_BACKUP_KEY en .env (docs/runbooks.md)." }
} else {
    Write-Host "Primera instalación en este equipo: no hay base que respaldar."
}

Step "Descargando la última versión"
if (Test-Path (Join-Path $root ".git")) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Falta Git: https://git-scm.com/download/win" }
    Push-Location $root
    git pull --ff-only
    $ok = $LASTEXITCODE -eq 0
    Pop-Location
    if (-not $ok) { throw "git pull no pudo avanzar (¿hay cambios locales?). Revisa con: git status" }
} else {
    Write-Host "Esta carpeta vino de un ZIP: descarga el ZIP nuevo de GitHub y cópialo encima (.env y data\ se conservan)," -ForegroundColor Yellow
    Write-Host "y luego vuelve a ejecutar actualizar.bat o instalar.bat." -ForegroundColor Yellow
}

& (Join-Path $PSScriptRoot "instalar.ps1")
Write-Host "`nActualización terminada. El respaldo previo quedó en backups\." -ForegroundColor Green
