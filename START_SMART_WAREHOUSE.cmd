@echo off
setlocal

title Smart Warehouse Pro Launcher
cd /d "%~dp0"

echo ========================================
echo   SMART WAREHOUSE - STARTING SYSTEM
echo ========================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
    echo [ERROR] Backend Python environment was not found.
    echo Run SETUP.cmd first. Expected: backend\.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo [ERROR] Frontend project was not found.
    echo Expected: frontend\package.json
    echo.
    pause
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Please install Node.js first.
    echo.
    pause
    exit /b 1
)

echo [1/3] Starting Backend at http://127.0.0.1:8010
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://127.0.0.1:8010/api/health' -TimeoutSec 2 -ErrorAction Stop | Out-Null;exit 0}catch{exit 1}"
if errorlevel 1 (
    start "Smart Warehouse Pro - Backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m alembic upgrade head && .venv\Scripts\python.exe -m app.seed && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010"
) else (
    echo Backend is already running.
)

echo [2/3] Starting Frontend at http://localhost:5180
powershell -NoProfile -Command "try{Invoke-WebRequest -Uri 'http://127.0.0.1:5180/' -TimeoutSec 2 -ErrorAction Stop | Out-Null;exit 0}catch{exit 1}"
if errorlevel 1 (
    start "Smart Warehouse Pro - Frontend" /D "%~dp0frontend" cmd /k "call npm run dev"
) else (
    echo Frontend is already running.
)

echo [3/3] Opening the website...
timeout /t 4 /nobreak >nul
start "" "http://localhost:5180/"

echo.
echo System windows have been opened successfully.
echo Close the Backend and Frontend windows to stop the system.
timeout /t 2 /nobreak >nul
endlocal
