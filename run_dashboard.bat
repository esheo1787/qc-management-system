@echo off
chcp 65001 > nul
echo ========================================
echo   QC Management System - Dashboard
echo ========================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [Warning] Virtual environment not found. Using system Python.
)

echo Starting Streamlit Dashboard...
echo Dashboard URL: http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard.
echo ========================================
echo.

python -m streamlit run dashboard.py

pause
