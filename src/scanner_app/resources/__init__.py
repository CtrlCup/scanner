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


def frozen_bundle_dir() -> Path | None:
    """Root-Verzeichnis des PyInstaller-Bundles (onefile: _MEIPASS-Extraktionsordner, onedir:
    der `_internal`-Ordner) — None bei einem Start aus dem Quellcode. Für mitgelieferte
    Ressourcen außerhalb des scanner_app-Pakets, z.B. die optional gebündelten OCR-Programme
    tesseract/qpdf/ghostscript (siehe ocr_engine.py und packaging/).
    """
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base is not None else None
