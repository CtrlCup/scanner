from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

_ORG = "scanner-app"
_APP = "Scanner"

DEFAULT_SAVE_DIR = Path.home() / "Documents" / "Scans"
DEFAULT_THEME = "system"
DEFAULT_ACCENT = "#0067C0"
ACCENT_SWATCHES = ["#0067C0", "#038387", "#744DA9", "#498205"]
DEFAULT_OCR_LANGUAGES = ["Deutsch", "Englisch"]


class AppSettings:
    """Dünner Wrapper um QSettings — persistiert plattformgerecht (Registry unter
    Windows, Konfigdatei unter Linux), ohne dass der Rest der App QSettings direkt anfasst.
    """

    def __init__(self) -> None:
        self._settings = QSettings(_ORG, _APP)

    @property
    def save_directory(self) -> Path:
        return Path(self._settings.value("save_directory", str(DEFAULT_SAVE_DIR)))

    @save_directory.setter
    def save_directory(self, value: Path) -> None:
        self._settings.setValue("save_directory", str(value))

    @property
    def ocr_enabled(self) -> bool:
        return self._settings.value("ocr_enabled", False, type=bool)

    @ocr_enabled.setter
    def ocr_enabled(self, value: bool) -> None:
        self._settings.setValue("ocr_enabled", value)

    @property
    def ocr_languages(self) -> list[str]:
        value = self._settings.value("ocr_languages", DEFAULT_OCR_LANGUAGES)
        if isinstance(value, str):
            return [value]
        return list(value)

    @ocr_languages.setter
    def ocr_languages(self, value: list[str]) -> None:
        self._settings.setValue("ocr_languages", value)

    @property
    def handwriting_enabled(self) -> bool:
        return self._settings.value("handwriting_enabled", False, type=bool)

    @handwriting_enabled.setter
    def handwriting_enabled(self, value: bool) -> None:
        self._settings.setValue("handwriting_enabled", value)

    @property
    def auto_rotate_enabled(self) -> bool:
        return self._settings.value("auto_rotate_enabled", False, type=bool)

    @auto_rotate_enabled.setter
    def auto_rotate_enabled(self, value: bool) -> None:
        self._settings.setValue("auto_rotate_enabled", value)

    @property
    def theme(self) -> str:
        return self._settings.value("theme", DEFAULT_THEME, type=str)

    @theme.setter
    def theme(self, value: str) -> None:
        self._settings.setValue("theme", value)

    @property
    def accent_color(self) -> str:
        return self._settings.value("accent_color", DEFAULT_ACCENT, type=str)

    @accent_color.setter
    def accent_color(self, value: str) -> None:
        self._settings.setValue("accent_color", value)

    @property
    def auto_update_check_enabled(self) -> bool:
        return self._settings.value("auto_update_check_enabled", True, type=bool)

    @auto_update_check_enabled.setter
    def auto_update_check_enabled(self, value: bool) -> None:
        self._settings.setValue("auto_update_check_enabled", value)

    @property
    def last_device_id(self) -> str | None:
        value = self._settings.value("last_device_id", "")
        return value or None

    @last_device_id.setter
    def last_device_id(self, value: str | None) -> None:
        self._settings.setValue("last_device_id", value or "")
