from __future__ import annotations

import sys

from scanner_app.backend.base import ScannerBackend


def get_backend() -> ScannerBackend:
    """Wählt die passende Scanner-Backend-Implementierung für die aktuelle Plattform.

    Der Import der plattformspezifischen Module erfolgt bewusst erst hier (nicht auf
    Paketebene), damit z.B. das Windows/WIA-Modul nie auf Linux importiert wird und
    umgekehrt — beide haben Abhängigkeiten, die nur auf ihrer Zielplattform installiert sind.
    """
    if sys.platform.startswith("linux"):
        from scanner_app.backend.linux_sane import SaneScannerBackend

        return SaneScannerBackend()
    if sys.platform == "win32":
        from scanner_app.backend.windows_wia import WiaScannerBackend

        return WiaScannerBackend()
    raise RuntimeError(f"Nicht unterstützte Plattform: {sys.platform}")
