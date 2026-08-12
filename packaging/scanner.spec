# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für die Scanner-App. Wird sowohl lokal (Linux-Pakete) als auch in
GitHub Actions (Windows-.exe) mit demselben Befehl verwendet:

    pyinstaller packaging/scanner.spec --distpath dist --workpath build

Windows baut bewusst als Onefile (eine einzelne Scanner.exe, kein Ordner drumherum) —
das ist es, was als ".exe" erwartet wird. Linux bleibt Onedir, da AppImage/deb/rpm ohnehin
einen Ordner erwarten und Onedir schneller startet (kein Selbst-Entpacken bei jedem Start).
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all

ONEFILE = sys.platform.startswith("win")

ROOT = os.path.dirname(os.path.abspath(SPECPATH))
SRC = os.path.join(ROOT, "src")
ICON_ICO = os.path.join(SRC, "scanner_app", "resources", "icon.ico")

# App-Icon (Taskbar/Titelleiste) wird zur Laufzeit über scanner_app.resources.resource_path
# geladen — muss daher als Datendatei mit ins Bundle, nicht nur als EXE-Icon.
datas = [(os.path.join(SRC, "scanner_app", "resources"), "scanner_app/resources")]
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

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="Scanner",
        console=False,
        icon=ICON_ICO,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Scanner",
        console=False,
        icon=ICON_ICO,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name="Scanner",
    )
