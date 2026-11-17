@echo off
REM Primera instalacion: dependencias, compilacion, .env y base de datos DEMO.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\instalar.ps1"
pause
