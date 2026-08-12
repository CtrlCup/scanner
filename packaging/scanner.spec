# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für die Scanner-App. Wird sowohl lokal (Linux-Pakete) als auch in
GitHub Actions (Windows-.exe) mit demselben Befehl verwendet:

    pyinstaller packaging/scanner.spec --distpath dist --workpath build
"""

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPECPATH))
SRC = os.path.join(ROOT, "src")

datas = []
binaries = []
hiddenimports = []

# ocrmypdf/pikepdf laden Teile ihrer Funktionalität über pluggy-Hooks/Dateidaten, die
# PyInstallers statische Bytecode-Analyse nicht zuverlässig erkennt.
for _pkg in ("ocrmypdf", "pikepdf"):
    _pkg_datas, _pkg_binaries, _pkg_hiddenimports = collect_all(_pkg)
    datas += _pkg_datas
    binaries += _pkg_binaries
    hiddenimports += _pkg_hiddenimports

a = Analysis(
    [os.path.join(SRC, "scanner_app", "main.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Scanner",
    console=False,
    icon=os.path.join(ROOT, "packaging", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Scanner",
)
