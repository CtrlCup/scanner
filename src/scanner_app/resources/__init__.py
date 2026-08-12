from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Pfad zu einer gebündelten Ressource — funktioniert sowohl beim Ausführen aus dem
    Quellcode als auch in einem PyInstaller-Bundle (onefile: _MEIPASS-Extraktionsverzeichnis,
    onedir: _internal-Ordner neben der ausführbaren Datei — PyInstaller setzt _MEIPASS dort
    ebenfalls auf das Verzeichnis, aus dem Datendateien gelesen werden müssen).
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "scanner_app" / "resources" / Path(*parts)
    return Path(__file__).parent / Path(*parts)
