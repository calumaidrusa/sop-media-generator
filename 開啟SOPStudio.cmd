@echo off
cd /d "%~dp0"
start "SOP Studio Server" /min cmd /c " .venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 4174"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:4174"
