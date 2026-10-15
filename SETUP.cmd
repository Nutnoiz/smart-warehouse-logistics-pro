@echo off
setlocal
cd /d "%~dp0"
echo Smart Warehouse Pro - first-time setup
where python >nul 2>&1
if errorlevel 1 goto missing_python
where npm.cmd >nul 2>&1
if errorlevel 1 goto missing_node
if not exist backend\.venv\Scripts\python.exe python -m venv backend\.venv
if errorlevel 1 goto failed
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
if errorlevel 1 goto failed
if not exist backend\.env copy backend\.env.example backend\.env >nul
cd frontend
call npm ci
if errorlevel 1 goto failed
echo Setup complete. Double-click START_SMART_WAREHOUSE.cmd
pause
exit /b 0
:missing_python
echo Python 3.12 or newer is required. Install Python with Add to PATH enabled.
goto failed
:missing_node
echo Node.js 22 or newer is required.
:failed
echo Setup failed. See the error above.
pause
exit /b 1
