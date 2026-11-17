@echo off
REM Abre EduMaster.ai en este equipo: la API sirve tambien la web en http://localhost:8000
cd /d "%~dp0apps\api"
start "" http://localhost:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
