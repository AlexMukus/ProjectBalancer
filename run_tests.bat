@echo off
echo ========================================
echo Running XML Parser Tests
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

echo [1/3] Checking Python installation...
python --version

echo.
echo [2/3] Checking pytest installation...
python -c "import pytest" > nul 2>&1
if errorlevel 1 (
    echo pytest is not installed. Installing...
    python -m pip install pytest>=7.0.0
    if errorlevel 1 (
        echo ERROR: Failed to install pytest
        pause
        exit /b 1
    )
) else (
    python -c "import pytest; print('pytest version:', pytest.__version__)"
)

echo.
echo [3/3] Running tests...
echo.

REM Run pytest with verbose output
python -m pytest tests/ -v

if errorlevel 1 (
    echo.
    echo ========================================
    echo Some tests failed. See output above.
    echo ========================================
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo All tests passed!
    echo ========================================
)

echo.
pause

