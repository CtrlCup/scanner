from __future__ import annotations

from pathlib import Path
from typing import Any

from scanner_app.backend.base import ColorMode, ScanOptions, ScannerBackend, ScannerDevice, ScanSource
from scanner_app.backend.exceptions import ScanFailedError

# SANE-Treiber unterscheiden sich stark in den unterstützten Optionsnamen/-werten
# (z.B. "Color"/"Gray" vs. "color"/"gray", "ADF"/"Automatic Document Feeder"). Wir setzen
# jede Option best-effort und ignorieren Treiber, die sie nicht kennen — siehe _try_set.
_MODE_BY_COLOR_MODE = {
    ColorMode.COLOR: "Color",
    ColorMode.GRAYSCALE: "Gray",
}
_SOURCE_KEYWORDS = {
    ScanSource.FLATBED: ("flatbed",),
    ScanSource.FEEDER: ("adf", "feeder", "automatic document feeder"),
}


class SaneScannerBackend(ScannerBackend):
    def __init__(self) -> None:
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        import sane

        sane.init()
        self._initialized = True

    def list_devices(self) -> list[ScannerDevice]:
        self._ensure_init()
        import sane

        devices = []
        for name, vendor, model, _dev_type in sane.get_devices():
            label = f"{vendor} {model}".strip() or name
            devices.append(ScannerDevice(device_id=name, display_name=label))
        return devices

    def scan_page(self, device: ScannerDevice, options: ScanOptions, output_path: Path) -> Path:
        self._ensure_init()
        import sane

        try:
            dev = sane.open(device.device_id)
        except Exception as exc:  # SANE wirft treiberspezifische Exceptions
            raise ScanFailedError(f"Scanner konnte nicht geöffnet werden: {exc}") from exc

        try:
            self._apply_options(dev, options)
            try:
                image = dev.scan()
            except Exception as exc:
                raise ScanFailedError(f"Scanvorgang fehlgeschlagen: {exc}") from exc

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            return output_path
        finally:
            dev.close()

    def _apply_options(self, dev: Any, options: ScanOptions) -> None:
        available = set(dev.opt.keys()) if hasattr(dev, "opt") else set()

        def try_set(name: str, value: Any) -> None:
            if name not in available:
                return
            try:
                setattr(dev, name, value)
            except Exception:
                pass  # Wert außerhalb des vom Treiber unterstützten Bereichs — best effort

        try_set("resolution", options.resolution_dpi)
        try_set("mode", _MODE_BY_COLOR_MODE[options.color_mode])
        try_set("brightness", options.brightness)
        try_set("contrast", options.contrast)

        if options.source is not ScanSource.AUTO and "source" in available:
            constraint = getattr(dev.opt["source"], "constraint", None) or []
            keywords = _SOURCE_KEYWORDS[options.source]
            match = next(
                (value for value in constraint if any(k in value.lower() for k in keywords)),
                None,
            )
            if match:
                try_set("source", match)

    def close(self) -> None:
        if self._initialized:
            import sane

            sane.exit()
            self._initialized = False
