@echo off
echo ===================================================
echo Starting Auth Service local development server...
echo URL: http://127.0.0.1:8000
echo ===================================================
set PYTHONPATH=.
call .venv\Scripts\activate.bat
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
