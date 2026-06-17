@echo off
title Auth Service Launcher
cls

:menu
cd "%~dp0"
echo ===================================================
echo        Auth Service Development Launcher
echo ===================================================
echo 1) Start Backend only (FastAPI on http://127.0.0.1:8000)
echo 2) Start Frontend only (Vite on http://127.0.0.1:5173)
echo 3) Start BOTH Backend and Frontend
echo 4) Run Backend tests (pytest)
echo 5) Exit
echo ===================================================
set /p choice="Choose an option (1-5): "

if "%choice%"=="1" goto backend
if "%choice%"=="2" goto frontend
if "%choice%"=="3" goto both
if "%choice%"=="4" goto tests
if "%choice%"=="5" goto exit
echo Invalid choice, try again.
pause
cls
goto menu

:backend
echo Starting Backend (FastAPI)...
cd backend
set PYTHONPATH=.
call .venv\Scripts\activate.bat
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
goto menu

:frontend
echo Starting Frontend (Vite)...
cd frontend
npm run dev
goto menu

:both
echo Launching Frontend in a new window...
start cmd /k "title Auth Service Frontend && cd frontend && npm run dev"
echo Starting Backend in this window...
cd backend
set PYTHONPATH=.
call .venv\Scripts\activate.bat
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
goto menu

:tests
echo Running Backend Tests...
cd backend
set PYTHONPATH=.
call .venv\Scripts\activate.bat
python -m pytest
pause
goto menu

:exit
exit
