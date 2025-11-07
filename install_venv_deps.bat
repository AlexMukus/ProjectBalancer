@echo off
echo ========================================
echo Installing dependencies in virtual environment
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please create it first: python -m venv .venv
    pause
    exit /b 1
)

echo Installing dependencies with pre-built binaries...
echo This prevents compilation errors on Windows
echo.

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --only-binary :all: streamlit pandas plotly lxml reportlab openpyxl altair Pillow

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS! Dependencies installed
echo ========================================
echo.
echo To run the app: .venv\Scripts\python.exe run_app.py
echo.
pause

