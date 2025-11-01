@echo off
echo ========================================
echo Building MS Project Analyzer to .exe
echo ========================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/5] Checking Python installation...
python --version

echo.
echo [2/5] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements_exe.txt

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [3/5] Cleaning previous build...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "MSProjectAnalyzer.exe" del /q "MSProjectAnalyzer.exe"

echo.
echo [4/5] Running PyInstaller...
echo This may take several minutes...
pyinstaller app.spec --clean

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo [5/5] Moving .exe file...
if exist "dist\MSProjectAnalyzer.exe" (
    move "dist\MSProjectAnalyzer.exe" "MSProjectAnalyzer.exe"
    echo.
    echo ========================================
    echo SUCCESS! File created: MSProjectAnalyzer.exe
    echo ========================================
    echo.
    echo File size:
    dir MSProjectAnalyzer.exe | find "MSProjectAnalyzer.exe"
    echo.
    echo To run: double-click MSProjectAnalyzer.exe
    echo The app will open in your browser automatically
) else (
    echo ERROR: MSProjectAnalyzer.exe not found in dist\
    echo Check PyInstaller logs above
)

echo.
pause
