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
echo Upgrading pip, wheel, and setuptools...
python -m pip install --upgrade pip wheel setuptools

echo.
echo Installing numpy with pre-built binaries (must be first)...
echo (This prevents compilation errors on Windows - no C++ compiler needed)
python -m pip install --only-binary :all: --upgrade numpy

if errorlevel 1 (
    echo ERROR: Failed to install numpy from pre-built binaries
    echo This usually means no compatible wheel is available for your Python version
    echo Python version info:
    python --version
    python -c "import platform; print('Architecture:', platform.architecture()[0])"
    echo.
    echo Solutions:
    echo 1. Try installing a compatible Python version (3.10, 3.11, 3.12 recommended)
    echo 2. Install Microsoft Visual C++ Build Tools to compile from source:
    echo    https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

echo Verifying numpy installation...
python -c "import numpy; print('numpy version:', numpy.__version__)" || (
    echo ERROR: numpy installation verification failed
    pause
    exit /b 1
)

echo.
echo Installing pandas and pyarrow with pre-built binaries...
python -m pip install --only-binary :all: --upgrade pandas pyarrow

if errorlevel 1 (
    echo ERROR: Failed to install pandas/pyarrow
    echo numpy is already installed, but pandas/pyarrow failed
    echo Try manually: python -m pip install --only-binary :all: --upgrade pandas pyarrow
    pause
    exit /b 1
)

echo.
echo Installing remaining dependencies...
echo (Skipping numpy, pandas, pyarrow as they are already installed)
echo Creating temporary requirements file without numpy, pandas, pyarrow...

REM Создаем временный файл requirements без numpy, pandas, pyarrow
python -c "import sys; lines = open('requirements_exe.txt').readlines(); filtered = [l for l in lines if not any(x in l.lower() for x in ['numpy', 'pandas', 'pyarrow'])]; open('requirements_temp.txt', 'w').writelines(filtered)"

echo.
echo Installing remaining packages with pre-built binaries...
echo (numpy, pandas, pyarrow are already installed and will be skipped)
python -m pip install --only-binary :all: -r requirements_temp.txt

REM Если установка с --only-binary не удалась, пробуем без этого флага
if errorlevel 1 (
    echo.
    echo WARNING: Some packages could not be installed with pre-built binaries
    echo Trying to install remaining dependencies without --only-binary flag...
    echo (This may attempt to reinstall numpy/pandas/pyarrow from source if needed)
    python -m pip install -r requirements_temp.txt
    
    REM Проверяем, что numpy все еще работает
    python -c "import numpy; print('numpy version:', numpy.__version__)" || (
        echo ERROR: numpy was broken during dependency installation
        echo Reinstalling numpy from pre-built binaries...
        python -m pip install --only-binary :all: --force-reinstall numpy
    )
    
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo.
        echo Solutions:
        echo 1. Make sure you have 64-bit Python installed
        echo 2. Install Microsoft Visual C++ Build Tools from:
        echo    https://visualstudio.microsoft.com/visual-cpp-build-tools/
        echo 3. Or try installing packages one by one to identify the problem
        del requirements_temp.txt 2>nul
        pause
        exit /b 1
    )
)

REM Удаляем временный файл
del requirements_temp.txt 2>nul

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
