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

REM ----- Start Cloudflare Tunnel (quick tunnel only) -----
REM This script now always uses a temporary quick tunnel (no certificate required).
REM The tunnel generates a random public URL each time the script runs.

echo Starting quick Cloudflare Tunnel (temporary URL)...
REM The output of the quick tunnel contains a line starting with "https://"
REM Capture that line and display it for the user.
for /f "tokens=*" %%A in ('cloudflared tunnel --url http://localhost:8000 ^| findstr /r "https://"') do (
    set "PUBLIC_URL=%%A"
    echo Public URL: %PUBLIC_URL%
)
REM Keep the quick tunnel running in a separate window
start "cloudflared" cloudflared tunnel --url http://localhost:8000

echo All services have been launched. Check each window for logs.
pause