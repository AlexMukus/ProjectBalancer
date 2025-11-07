"""
Launcher script для запуска Streamlit приложения через PyInstaller
Этот файл решает проблему "must be run with streamlit run"
"""
import sys
import os
import socket

# Попытка импорта Streamlit CLI с fallback вариантами
stcli = None
import_error = None

# Вариант 1: прямой импорт streamlit.web.cli (работает в Streamlit 1.50.0+)
try:
    import streamlit.web.cli as stcli
except ImportError as e:
    import_error = str(e)
    # Вариант 2: from streamlit.web import cli
    try:
        from streamlit.web import cli as stcli
    except ImportError as e2:
        import_error = str(e2)
        # Вариант 3: from streamlit import cli
        try:
            from streamlit import cli as stcli
        except ImportError as e3:
            import_error = str(e3)
            stcli = None

if stcli is None:
    print("ОШИБКА: Не удалось импортировать Streamlit CLI")
    print(f"Детали ошибки: {import_error}")
    print(f"Python путь: {sys.path}")
    print(f"Python версия: {sys.version}")
    try:
        import streamlit
        print(f"Streamlit установлен: {streamlit.__version__}")
    except ImportError:
        print("Streamlit НЕ установлен")
        print("Установите: pip install streamlit")
    sys.exit(1)

def get_base_path():
    """Определяет базовый путь для frozen и обычного режима"""
    if getattr(sys, 'frozen', False):
        # Если запущено через PyInstaller
        # sys._MEIPASS - временная папка с распакованными файлами
        # sys.executable - путь к .exe файлу
        # Базовый путь - директория, где находится .exe
        if hasattr(sys, '_MEIPASS'):
            # Для однофайловой сборки
            base_path = os.path.dirname(sys.executable)
        else:
            # Для многофайловой сборки
            base_path = os.path.dirname(sys.executable)
    else:
        # Если запущено напрямую через Python
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return base_path

def get_app_path():
    """Определяет путь к app.py"""
    if getattr(sys, 'frozen', False):
        # В frozen приложении app.py находится в sys._MEIPASS
        if hasattr(sys, '_MEIPASS'):
            app_path = os.path.join(sys._MEIPASS, 'app.py')
            if os.path.exists(app_path):
                return app_path
        # Fallback: ищем рядом с .exe
        base_path = os.path.dirname(sys.executable)
        app_path = os.path.join(base_path, 'app.py')
        if os.path.exists(app_path):
            return app_path
    else:
        # В обычном режиме app.py в той же директории
        base_path = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(base_path, 'app.py')
        if os.path.exists(app_path):
            return app_path
    
    # Если не нашли, возвращаем предполагаемый путь
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'app.py')
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')

def is_port_available(port, host='localhost'):
    """Проверяет, доступен ли порт"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return True  # Порт свободен, если bind успешен
            except OSError:
                return False  # Порт занят
    except Exception:
        return False

def find_free_port(start_port=8501, max_attempts=100):
    """Находит свободный порт, начиная с start_port"""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    # Если не нашли свободный порт, возвращаем начальный
    # Streamlit сам попробует найти свободный порт
    return start_port

if __name__ == '__main__':
    try:
        # Получить путь к app.py
        app_path = get_app_path()
        
        # Проверить существование app.py
        if not os.path.exists(app_path):
            print(f"ОШИБКА: Файл app.py не найден по пути: {app_path}")
            print(f"Текущая рабочая директория: {os.getcwd()}")
            if getattr(sys, 'frozen', False):
                print(f"Frozen режим: sys._MEIPASS = {getattr(sys, '_MEIPASS', 'N/A')}")
                print(f"sys.executable = {sys.executable}")
            sys.exit(1)
        
        # Установить рабочую директорию на базовый путь для корректной работы путей
        base_path = get_base_path()
        if base_path and os.path.exists(base_path):
            os.chdir(base_path)
        
        # Найти свободный порт
        # Проверяем порт 8501
        if not is_port_available(8501):
            # Порт 8501 занят, ищем свободный порт
            port = find_free_port(8502)
            print(f"Порт 8501 занят, используется порт {port}")
        else:
            port = 8501
        
        # Проверим еще раз перед запуском, так как порт мог быть занят между проверкой и запуском
        if not is_port_available(port):
            port = find_free_port(port + 1)
            print(f"Порт был занят, используется порт {port}")
        
        print(f"Запуск Streamlit на порту {port}")
        
        # Настроить аргументы для Streamlit CLI
        # Отключаем режим разработки и используем автоматический выбор порта
        # Используем --server.port с явным указанием порта
        sys.argv = [
            "streamlit", "run", app_path,
            "--global.developmentMode=false",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.port", str(port),
            "--server.address", "localhost"
        ]
        
        # Запустить Streamlit
        sys.exit(stcli.main())
        
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА при запуске приложения: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
