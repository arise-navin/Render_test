@echo off
echo ==================================
echo ServiceNow AI Copilot - Launcher
echo ==================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Run setup check
echo.
echo Running setup check...
python setup.py

REM Ask if user wants to start the server
echo.
set /p start="Start the server now? (y/n): "

if /i "%start%"=="y" (
    echo.
    echo Starting ServiceNow AI Copilot...
    echo Dashboard: http://127.0.0.1:8000/
    echo Press CTRL+C to stop
    echo.
    python -m uvicorn main:app --reload
)

pause
