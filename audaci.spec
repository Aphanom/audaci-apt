# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import sys

datas = [('assets', 'assets'), ('model', 'model')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('vosk')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Умный выбор иконки под текущую ОС
if sys.platform == 'win32':
    icon_file = 'assets/icon.ico'
elif sys.platform == 'darwin':
    icon_file = 'assets/icon.icns'
else:
    icon_file = 'assets/icon.png'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='audaci',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# Упаковка в полноценное приложение для macOS
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Audaci.app',
        icon=icon_file,
        bundle_identifier='com.aphanom.audaci'
    )