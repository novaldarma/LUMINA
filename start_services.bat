@echo off
REM ------------------------------------------------------------
REM  Start Services Script for LUMINA Project
REM  - Activates the Python virtual environment
REM  - Launches the FastAPI backend (uvicorn)
REM  - Opens an ngrok tunnel exposing port 8000
REM  - Starts a Cloudflare Tunnel (cloudflared) pointing to the backend
REM ------------------------------------------------------------

REM ----- Activate virtual environment -----
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found. Ensure you have created it with "python -m venv venv".
)

REM ----- Start FastAPI backend -----
echo Starting FastAPI backend on http://0.0.0.0:8000 ...
start "FastAPI" uvicorn backend.main:app --host 0.0.0.0 --port 8000

REM Give the backend a moment to start before opening tunnels
timeout /t 5 /nobreak > nul

REM ----- Start ngrok tunnel -----
echo Starting ngrok tunnel for port 8000 ...
start "ngrok" ngrok http 8000

REM ----- Start Cloudflare Tunnel -----
REM Ensure cloudflared is installed and accessible via PATH.
echo Starting Cloudflare Tunnel (cloudflared) for http://localhost:8000 ...
start "cloudflared" cloudflared tunnel --url http://localhost:8000

echo All services have been launched. Check each window for logs.
pause