# Demostración pública con Cloudflare Tunnel (decisión D03). No es producción.
#   powershell -ExecutionPolicy Bypass -File infra\scripts\exponer.ps1
#
# Qué hace:
#   1. Compila la web si hace falta.
#   2. Arranca la API en modo demo (cookies solo por HTTPS, IP real desde Cloudflare). La API sirve la web.
#   3. Abre un Quick Tunnel (sin cuenta) hacia el puerto 8000 y muestra la dirección pública.
# Para terminar: Ctrl+C en esta ventana (cierra el túnel y la API).

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"

$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared -and (Test-Path "C:\Program Files (x86)\cloudflared\cloudflared.exe")) {
    $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
}
if (-not $cloudflared) { throw "Falta cloudflared: winget install --id Cloudflare.cloudflared" }
if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    throw "El puerto 8000 está en uso: cierra iniciar.bat antes de la demo."
}

if (-not (Test-Path (Join-Path $web "dist\index.html"))) {
    Push-Location $web; npm run build; Pop-Location
}

$env:EDUMASTER_ENVIRONMENT = "demo"
$env:EDUMASTER_COOKIE_SECURE = "true"
$env:EDUMASTER_TRUST_CLOUDFLARE_IP = "true"
$apiProcess = Start-Process -FilePath (Join-Path $api ".venv\Scripts\python.exe") -PassThru -NoNewWindow `
    -WorkingDirectory $api -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000")

try {
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try { Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health/ready" -UseBasicParsing -TimeoutSec 3 | Out-Null; break }
        catch { Start-Sleep 1 }
    }
    # Smoke test (D44): no se publica a ciegas. Si algo falla se avisa, pero la demo no se bloquea.
    & (Join-Path $api ".venv\Scripts\python.exe") (Join-Path $api "scripts\smoke.py") --url http://127.0.0.1:8000
    if ($LASTEXITCODE -ne 0) { Write-Host "AVISO: el smoke test encontró fallos (ver arriba). Revisa docs/runbooks.md." -ForegroundColor Yellow }
    Write-Host "`nAbriendo túnel... la dirección pública aparece abajo (https://...trycloudflare.com)." -ForegroundColor Cyan
    & $cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000
} finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force }
}
