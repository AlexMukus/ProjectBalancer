@echo off
chcp 65001 > nul
echo ========================================
echo Сборка MS Project Analyzer в .exe файл
echo ========================================
echo.

REM Проверка наличия Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не установлен или не добавлен в PATH
    echo Установите Python 3.10 или выше с сайта python.org
    pause
    exit /b 1
)

echo [1/5] Проверка Python установлен...
python --version

echo.
echo [2/5] Установка зависимостей...
python -m pip install --upgrade pip
python -m pip install -r requirements_exe.txt

if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo [3/5] Очистка предыдущей сборки...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "MSProjectAnalyzer.exe" del /q "MSProjectAnalyzer.exe"

echo.
echo [4/5] Запуск PyInstaller...
echo Это может занять несколько минут...
pyinstaller app.spec --clean

if errorlevel 1 (
    echo ОШИБКА: Сборка не удалась
    pause
    exit /b 1
)

echo.
echo [5/5] Перемещение .exe файла...
if exist "dist\MSProjectAnalyzer.exe" (
    move "dist\MSProjectAnalyzer.exe" "MSProjectAnalyzer.exe"
    echo.
    echo ========================================
    echo УСПЕШНО! Файл создан: MSProjectAnalyzer.exe
    echo ========================================
    echo.
    echo Размер файла:
    dir MSProjectAnalyzer.exe | find "MSProjectAnalyzer.exe"
    echo.
    echo Для запуска: дважды кликните по MSProjectAnalyzer.exe
    echo Приложение откроется в браузере автоматически
) else (
    echo ОШИБКА: Файл MSProjectAnalyzer.exe не найден в dist\
    echo Проверьте логи PyInstaller выше
)

echo.
pause
