class ScannerBackendError(Exception):
    """Basisklasse für alle Fehler beim Zugriff auf Scanner-Hardware."""


class NoScannerFoundError(ScannerBackendError):
    """Kein passender Scanner im Betriebssystem gefunden."""


class ScanFailedError(ScannerBackendError):
    """Der Scanvorgang selbst ist fehlgeschlagen (z.B. Papierstau, Gerät offline)."""
