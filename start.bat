@echo off
echo ============================================================
echo    Medical Report Analyzer - One-Click Launcher
echo    AI-Powered Medical Intelligence Platform
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

:: Create .env if not exists
if not exist .env (
    echo [SETUP] Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo [WARNING] Please edit .env and add your GEMINI_API_KEY
    echo          Get a free key at: https://aistudio.google.com/apikey
    echo          Demo mode works without an API key.
    echo.
)

:: Install Python dependencies
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Some Python packages may have failed. The app will still run with fallbacks.
)

:: Install frontend dependencies
echo [2/4] Installing frontend dependencies...
cd frontend
call npm install --silent
if errorlevel 1 (
    echo [ERROR] npm install failed!
    pause
    exit /b 1
)
cd ..

:: Start Backend (in background)
echo [3/4] Starting FastAPI backend on http://localhost:8000 ...
start /B cmd /c "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend to start
echo Waiting for backend to start...
timeout /t 4 /nobreak >nul

:: Start Frontend
echo [4/4] Starting React frontend on http://localhost:5173 ...
cd frontend
start /B cmd /c "npm run dev"
cd ..

:: Wait a moment then open browser
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo    Application is running!
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo    Press Ctrl+C to stop, or close this window.
echo ============================================================
echo.

:: Open browser
start http://localhost:5173

:: Keep window open
pause
