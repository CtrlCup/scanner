from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ScanSource(Enum):
    AUTO = "auto"
    FLATBED = "flatbed"
    FEEDER = "feeder"  # Einzug / ADF


class ColorMode(Enum):
    COLOR = "color"
    GRAYSCALE = "grayscale"  # UI-Label "Schwarz-Weiß"


@dataclass
class ScannerDevice:
    device_id: str
    display_name: str


@dataclass
class ScanOptions:
    source: ScanSource = ScanSource.AUTO
    color_mode: ColorMode = ColorMode.COLOR
    resolution_dpi: int = 300
    brightness: int = 0
    contrast: int = 0
    auto_enhance: bool = True
    auto_enhance_strength: int = 40


class ScannerBackend(ABC):
    """Zugriff auf im Betriebssystem hinterlegte Scanner, hinter einer Schnittstelle,
    die die UI-Schicht nie plattformabhängig verzweigen lassen muss.
    """

    @abstractmethod
    def list_devices(self) -> list[ScannerDevice]:
        """Alle aktuell im Betriebssystem verfügbaren Scanner/Drucker mit Scanfunktion."""

    @abstractmethod
    def scan_page(
        self, device: ScannerDevice, options: ScanOptions, output_path: Path
    ) -> Path:
        """Scannt eine Seite und schreibt sie als Bilddatei nach output_path."""

    def close(self) -> None:
        """Gibt vom Backend gehaltene Ressourcen frei (Gerätehandles, COM, ...)."""
        return None
