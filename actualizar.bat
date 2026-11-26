@echo off
REM Actualiza a la ultima version de GitHub sin perder datos: respaldo, git pull e instalacion (docs/despliegue.md).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\actualizar.ps1"
pause
