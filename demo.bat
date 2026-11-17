@echo off
REM Demostracion publica con Cloudflare Tunnel. Ctrl+C para terminar.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\exponer.ps1"
pause
