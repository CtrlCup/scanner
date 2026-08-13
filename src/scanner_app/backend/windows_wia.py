from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from scanner_app.backend.base import (
    ColorMode,
    ScannerBackend,
    ScannerDevice,
    ScanOptions,
    ScanSource,
)
from scanner_app.backend.exceptions import NoScannerFoundError, ScanFailedError

_logger = logging.getLogger(__name__)

# ACHTUNG: Diese Implementierung wurde in einer Linux-Dev-Umgebung ohne Windows-Rechner
# geschrieben und konnte nicht gegen echte Hardware/COM getestet werden. Property-IDs und
# -Konstanten stammen aus der offiziellen WIA-Automation-Referenz (wiadef.h):
# https://learn.microsoft.com/windows/win32/wia/-wia-scanner-properties
# Vor Produktiveinsatz unbedingt mit einem echten WIA-Scanner unter Windows verifizieren.

_WIA_DEVICE_TYPE_SCANNER = 1

_PROP_HORIZONTAL_RESOLUTION = 6147
_PROP_VERTICAL_RESOLUTION = 6148
_PROP_BRIGHTNESS = 6154
_PROP_CONTRAST = 6155
_PROP_CURRENT_INTENT = 6146
_PROP_DOCUMENT_HANDLING_SELECT = 3088

_INTENT_COLOR = 1
_INTENT_GRAYSCALE = 2

_DOCUMENT_HANDLING_FEEDER = 1
_DOCUMENT_HANDLING_FLATBED = 2

_FORMAT_ID_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"


class WiaScannerBackend(ScannerBackend):
    """WIA/COM-Objekte sind apartment-gebunden (STA) — ein `WIA.DeviceManager`, der im
    UI-Thread erzeugt wurde (z.B. beim Befüllen der Geräteliste), darf nicht direkt aus dem
    Scan-Hintergrund-Thread (siehe `MainWindow._ScanWorker`) weiterverwendet werden. Ohne
    korrekte Marshalling-Vorkehrung kann ein solcher Cross-Thread-COM-Zugriff je nach
    Windows-Version/Treiber entweder sofort einen Fehler werfen oder — schlimmer — den
    aufrufenden Thread unbegrenzt blockieren, ohne dass eine Exception fällt (ein einfacher
    try/except in `_ScanWorker.run()` würde das also nicht auffangen). `self._local`
    (threading.local) sorgt dafür, dass jeder Thread sein eigenes, in diesem Thread per
    `CoInitialize()` initialisiertes DeviceManager-COM-Objekt bekommt.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _manager(self) -> Any:
        manager = getattr(self._local, "device_manager", None)
        if manager is None:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            manager = win32com.client.Dispatch("WIA.DeviceManager")
            self._local.device_manager = manager
        return manager

    def list_devices(self) -> list[ScannerDevice]:
        manager = self._manager()
        devices = []
        for info in manager.DeviceInfos:
            if info.Type != _WIA_DEVICE_TYPE_SCANNER:
                continue
            try:
                name = info.Properties("Name").Value
            except Exception:
                _logger.debug("WIA-Gerätename nicht lesbar für %s", info.DeviceID, exc_info=True)
                name = info.DeviceID
            devices.append(ScannerDevice(device_id=info.DeviceID, display_name=name))
        return devices

    def scan_page(self, device: ScannerDevice, options: ScanOptions, output_path: Path) -> Path:
        manager = self._manager()
        index = self._index_for(manager, device.device_id)

        try:
            wia_device = manager.DeviceInfos(index).Connect()
        except Exception as exc:
            raise ScanFailedError(f"Scanner konnte nicht geöffnet werden: {exc}") from exc

        item = wia_device.Items[1]
        self._apply_options(item, options)

        try:
            image = item.Transfer(_FORMAT_ID_PNG)
        except Exception as exc:
            raise ScanFailedError(f"Scanvorgang fehlgeschlagen: {exc}") from exc

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        image.SaveFile(str(output_path))
        return output_path

    def _index_for(self, manager: Any, device_id: str) -> int:
        for i in range(1, manager.DeviceInfos.Count + 1):
            if manager.DeviceInfos(i).DeviceID == device_id:
                return i
        raise NoScannerFoundError(f"Scanner {device_id} nicht gefunden.")

    def _apply_options(self, item: Any, options: ScanOptions) -> None:
        def try_set(prop_id: int, value: Any) -> None:
            try:
                item.Properties(prop_id).Value = value
            except Exception:
                _logger.debug("WIA-Property %s=%r vom Gerät abgelehnt", prop_id, value, exc_info=True)

        try_set(_PROP_HORIZONTAL_RESOLUTION, options.resolution_dpi)
        try_set(_PROP_VERTICAL_RESOLUTION, options.resolution_dpi)
        try_set(
            _PROP_CURRENT_INTENT,
            _INTENT_COLOR if options.color_mode is ColorMode.COLOR else _INTENT_GRAYSCALE,
        )
        try_set(_PROP_BRIGHTNESS, options.brightness)
        try_set(_PROP_CONTRAST, options.contrast)

        if options.source is ScanSource.FEEDER:
            try_set(_PROP_DOCUMENT_HANDLING_SELECT, _DOCUMENT_HANDLING_FEEDER)
        elif options.source is ScanSource.FLATBED:
            try_set(_PROP_DOCUMENT_HANDLING_SELECT, _DOCUMENT_HANDLING_FLATBED)

    def close(self) -> None:
        # Räumt nur das COM-Objekt des aufrufenden (UI-)Threads auf — ein evtl. noch
        # laufender Scan-Hintergrund-Thread hat sein eigenes und wird beim Thread-Ende von
        # Windows selbst aufgeräumt.
        self._local.device_manager = None
