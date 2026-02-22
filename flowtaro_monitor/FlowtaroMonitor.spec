# PyInstaller spec – build: pyinstaller flowtaro_monitor/FlowtaroMonitor.spec
# Uruchom z katalogu głównego ACM.
# Wynik: dist/FlowtaroMonitor.exe (skopiuj do roota ACM i uruchom).
# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Katalog ACM (parent flowtaro_monitor)
acm_root = Path(SPECPATH).resolve().parent
# Ikona: umieść FlowtaroMonitor.ico w flowtaro_monitor/ i odkomentuj:
# icon_path = str(acm_root / "flowtaro_monitor" / "FlowtaroMonitor.ico")

a = Analysis(
    [str(acm_root / "flowtaro_monitor" / "main.py")],
    pathex=[str(acm_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "flowtaro_monitor._config",
        "flowtaro_monitor._monitor_data",
        "flowtaro_monitor._run_scripts",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["streamlit"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FlowtaroMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # bez okna konsoli (tylko GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
