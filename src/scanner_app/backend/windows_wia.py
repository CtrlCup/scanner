from __future__ import annotations

from pathlib import Path
from typing import Any

from scanner_app.backend.base import ColorMode, ScanOptions, ScannerBackend, ScannerDevice, ScanSource
from scanner_app.backend.exceptions import NoScannerFoundError, ScanFailedError

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
    def __init__(self) -> None:
        self._device_manager = None

    def _manager(self) -> Any:
        if self._device_manager is None:
            import win32com.client

            self._device_manager = win32com.client.Dispatch("WIA.DeviceManager")
        return self._device_manager

    def list_devices(self) -> list[ScannerDevice]:
        manager = self._manager()
        devices = []
        for info in manager.DeviceInfos:
            if info.Type != _WIA_DEVICE_TYPE_SCANNER:
                continue
            try:
                name = info.Properties("Name").Value
            except Exception:
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
                pass  # Gerät/Treiber unterstützt diese Eigenschaft nicht — best effort

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
        self._device_manager = None
