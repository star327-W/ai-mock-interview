@echo off
cd /d "%~dp0"
title Mock Interview Launcher

REM 优先使用指定路径的 Python,找不到则退回 PATH 中的 python
set "PYTHON=E:\Python\ruanjian\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ============================================
echo   Mock Interview AI Assistant - Launcher
echo ============================================
echo.
echo   Python: %PYTHON%
echo.

REM ---------- Backend (port 8000) ----------
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 (
    echo   [OK] Backend already running on port 8000
) else (
    echo   [..] Starting backend ...
    start "MockInterview-Backend" cmd /k "cd /d %~dp0backend && %PYTHON% -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

REM ---------- Frontend (port 5173) ----------
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 (
    echo   [OK] Frontend already running on port 5173
) else (
    echo   [..] Starting frontend ...
    start "MockInterview-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
)

echo.
echo   [..] Waiting for services to be ready ...
timeout /t 10 /nobreak >nul

echo   [..] Opening browser ...
start "" http://localhost:5173

echo.
echo ============================================
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8000
echo   API docs : http://localhost:8000/docs
echo.
echo   Close the two black windows to stop.
echo   This window can be closed.
echo ============================================
timeout /t 8 >nul
