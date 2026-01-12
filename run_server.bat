@echo off
chcp 65001 > nul
echo ========================================
echo   QC Management System - API Server
echo ========================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [Warning] Virtual environment not found. Using system Python.
)

echo Starting FastAPI server...
echo API URL: http://127.0.0.1:8000
echo API Docs: http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ========================================
echo.

python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
