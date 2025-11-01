# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file для сборки Streamlit приложения в .exe

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Собрать все скрытые импорты для Streamlit и зависимостей
hiddenimports = [
    'streamlit',
    'streamlit.web.cli',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'pandas',
    'plotly',
    'lxml',
    'lxml.etree',
    'lxml._elementpath',
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.pdfbase',
    'reportlab.pdfbase.ttfonts',
    'openpyxl',
    'altair',
    'pyarrow',
    'click',
    'toml',
    'validators',
    'watchdog',
    'tornado',
    'tzdata',
]

# Собрать все подмодули Streamlit
hiddenimports += collect_submodules('streamlit')
hiddenimports += collect_submodules('altair')

# Собрать файлы данных Streamlit
datas = []
datas += collect_data_files('streamlit')
datas += collect_data_files('altair')

# Добавить файлы проекта
datas += [('app.py', '.')]
datas += [('md3_components.py', '.')]
datas += [('.streamlit/config.toml', '.streamlit')]

block_cipher = None

a = Analysis(
    ['run_app.py'],  # Используем launcher вместо app.py напрямую
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'PIL'],  # Исключить ненужные библиотеки
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MSProjectAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Показывать консоль для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Можно добавить иконку: icon='app.ico'
)
