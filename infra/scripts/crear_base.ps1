# Crea la base PostgreSQL local de EduMaster.ai y la conecta en el .env.
# Uso: powershell -ExecutionPolicy Bypass -File infra\scripts\crear_base.ps1
# Pide la contraseña del usuario "postgres" (administrador de PostgreSQL); no la guarda.
# Crea el usuario "edumaster" con una contraseña aleatoria y la base "edumaster".

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$psql = (Get-Command psql -ErrorAction SilentlyContinue).Source
if (-not $psql) {
    $psql = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $psql) { throw "No se encontró psql. Instala PostgreSQL 16 o superior." }

$secure = Read-Host "Contraseña del usuario postgres" -AsSecureString
$env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))

$appPassword = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })

$exists = & $psql -h localhost -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='edumaster'"
if ($exists -eq "1") {
    & $psql -h localhost -U postgres -c "ALTER ROLE edumaster WITH LOGIN PASSWORD '$appPassword';" | Out-Null
} else {
    & $psql -h localhost -U postgres -c "CREATE ROLE edumaster WITH LOGIN PASSWORD '$appPassword';" | Out-Null
}
$db = & $psql -h localhost -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='edumaster'"
if ($db -ne "1") { & $psql -h localhost -U postgres -c "CREATE DATABASE edumaster OWNER edumaster;" | Out-Null }
Remove-Item Env:PGPASSWORD

# Escribe o reemplaza la URL en el .env.
$envFile = Join-Path $root ".env"
$url = "EDUMASTER_DATABASE_URL=postgresql+psycopg://edumaster:$appPassword@localhost:5432/edumaster"
$lines = @()
if (Test-Path $envFile) { $lines = Get-Content $envFile | Where-Object { $_ -notmatch "^EDUMASTER_DATABASE_URL=" } }
($lines + $url) | Set-Content -Path $envFile -Encoding utf8

Push-Location (Join-Path $root "apps\api")
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.seed
Pop-Location
Write-Host "PostgreSQL listo: base 'edumaster' con migraciones y cuentas DEMO." -ForegroundColor Green
