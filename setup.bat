@echo off
chcp 65001 > nul
echo ========================================
echo   QC Management System - Initial Setup
echo ========================================
echo.

REM Check Python version
python --version 2>nul
if errorlevel 1 (
    echo [Error] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Step 1: Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [Error] Failed to create virtual environment.
    pause
    exit /b 1
)

echo.
echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Step 3: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [Error] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Step 4: Creating data directory...
if not exist "data" mkdir data

echo.
echo Step 5: Initializing database with seed data...
python seed.py
if errorlevel 1 (
    echo [Warning] Seed script failed. Database may already exist.
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Run 'run_server.bat' to start the API server
echo   2. Run 'run_dashboard.bat' to start the Dashboard
echo.
echo IMPORTANT: Save the API keys displayed above!
echo ========================================
pause
