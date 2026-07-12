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

REM ----- Start Cloudflare Tunnel (static URL) -----
REM The free Cloudflare Tunnel generates a random URL each time. To obtain a permanent URL,
REM you need to create a named tunnel and bind it to a custom domain you control.
REM See the documentation in the repository (cloudflared.yml) for details.
REM Once the tunnel "lumina" is created and DNS is configured, you can start it with:
echo Starting static Cloudflare Tunnel (cloudflared) for http://localhost:8000 ...
start "cloudflared" cloudflared tunnel run lumina

echo All services have been launched. Check each window for logs.
pause