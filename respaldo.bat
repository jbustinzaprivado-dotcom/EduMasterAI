@echo off
REM Respaldo cifrado de la base y prueba de restauracion (D42). Ver docs/runbooks.md.
cd /d "%~dp0apps\api"
.venv\Scripts\python.exe -m app.backup crear
if errorlevel 1 goto fin
for /f "delims=" %%f in ('dir /b /o-d "%~dp0backups\*.emb"') do (
  .venv\Scripts\python.exe -m app.backup verificar "%~dp0backups\%%f"
  goto fin
)
:fin
pause
