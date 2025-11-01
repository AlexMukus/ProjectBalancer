"""
Launcher script для запуска Streamlit приложения через PyInstaller
Этот файл решает проблему "must be run with streamlit run"
"""
import sys
import os
from streamlit.web import cli as stcli

if __name__ == '__main__':
    # Получить путь к app.py (в той же директории)
    if getattr(sys, 'frozen', False):
        # Если запущено через PyInstaller
        application_path = sys._MEIPASS
    else:
        # Если запущено напрямую через Python
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    app_path = os.path.join(application_path, 'app.py')
    
    # Настроить аргументы для Streamlit CLI
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    
    # Запустить Streamlit
    sys.exit(stcli.main())
