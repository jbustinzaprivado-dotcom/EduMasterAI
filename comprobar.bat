@echo off
REM Smoke test: comprueba que EduMaster.ai en marcha responde bien (D44). Uso: comprobar.bat [URL]
cd /d "%~dp0apps\api"
if "%~1"=="" (.venv\Scripts\python.exe scripts\smoke.py) else (.venv\Scripts\python.exe scripts\smoke.py --url %1)
pause
