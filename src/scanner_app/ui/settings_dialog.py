from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scanner_app import __version__
from scanner_app.app_settings import ACCENT_SWATCHES, AppSettings
from scanner_app.ocr.language_manager import (
    AVAILABLE_LANGUAGES,
    download_language,
    is_language_installed,
)
from scanner_app.ui.widgets.segmented_control import SegmentedControl
from scanner_app.ui.widgets.toggle_switch import ToggleSwitch

_THEME_LABELS = {"Hell": "light", "Dunkel": "dark", "Automatisch": "system"}
_THEME_LABELS_REVERSE = {v: k for k, v in _THEME_LABELS.items()}


class _LanguageDownloadWorker(QObject):
    finished = Signal(str, bool)

    def __init__(self, display_name: str) -> None:
        super().__init__()
        self._display_name = display_name

    def run(self) -> None:
        try:
            download_language(self._display_name)
            self.finished.emit(self._display_name, True)
        except Exception:  # noqa: BLE001 - jeder Download-Fehler (Netzwerk, IO, ...) zählt als Fehlschlag
            self.finished.emit(self._display_name, False)


class SettingsDialog(QDialog):
    """Gear-Icon-Dialog: OCR an/aus + Sprachauswahl (Chips mit Installiert-Status,
    On-Demand-Hintergrund-Download), Theme, Akzentfarbe, Footer.
    """

    accentChanged = Signal(str)
    themeChanged = Signal(str)
    ocrSettingsChanged = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(420)
        self._settings = settings
        self._threads: list[QThread] = []
        self._language_chips: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        ocr_row = QHBoxLayout()
        ocr_label = QLabel("OCR-Texterkennung")
        ocr_label.setProperty("role", "sectionLabel")
        ocr_row.addWidget(ocr_label)
        ocr_row.addStretch()
        self._ocr_toggle = ToggleSwitch(accent=settings.accent_color)
        self._ocr_toggle.setChecked(settings.ocr_enabled)
        self._ocr_toggle.toggled.connect(self._on_ocr_toggled)
        ocr_row.addWidget(self._ocr_toggle)
        layout.addLayout(ocr_row)

        self._language_section = QWidget()
        language_layout = QVBoxLayout(self._language_section)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_hint = QLabel("Primärsprachen (Mehrfachauswahl, werden bei Bedarf heruntergeladen)")
        language_hint.setProperty("role", "hint")
        language_hint.setWordWrap(True)
        language_layout.addWidget(language_hint)

        chip_grid = QGridLayout()
        chip_grid.setSpacing(6)
        columns = 3
        selected = set(settings.ocr_languages)
        for index, name in enumerate(AVAILABLE_LANGUAGES):
            chip = QPushButton()
            chip.setObjectName("languageChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setChecked(name in selected)
            chip.clicked.connect(lambda _checked, n=name: self._on_language_toggled(n))
            self._language_chips[name] = chip
            self._refresh_chip_label(name)
            chip_grid.addWidget(chip, index // columns, index % columns)
        language_layout.addLayout(chip_grid)
        layout.addWidget(self._language_section)
        self._language_section.setVisible(settings.ocr_enabled)

        layout.addWidget(self._separator())

        theme_label = QLabel("DARSTELLUNG")
        theme_label.setProperty("role", "sectionLabel")
        layout.addWidget(theme_label)
        self._theme_control = SegmentedControl(list(_THEME_LABELS.keys()))
        self._theme_control.set_current(_THEME_LABELS_REVERSE.get(settings.theme, "Automatisch"))
        self._theme_control.currentChanged.connect(self._on_theme_changed)
        layout.addWidget(self._theme_control)

        accent_label = QLabel("AKZENTFARBE")
        accent_label.setProperty("role", "sectionLabel")
        layout.addWidget(accent_label)
        accent_row = QHBoxLayout()
        for color in ACCENT_SWATCHES:
            swatch = QPushButton()
            swatch.setFixedSize(28, 28)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setStyleSheet(
                f"background-color: {color}; border-radius: 14px; "
                f"border: 2px solid {'white' if color == settings.accent_color else 'transparent'};"
            )
            swatch.clicked.connect(lambda _checked, c=color: self._on_accent_selected(c))
            accent_row.addWidget(swatch)
        accent_row.addStretch()
        layout.addLayout(accent_row)

        layout.addWidget(self._separator())
        year = datetime.now().year  # noqa: DTZ005 - bewusst lokales Jahr für die Fußzeile
        footer = QLabel(f"Mit ❤ von Alex entwickelt · v{__version__} · {year}")
        footer.setProperty("role", "hint")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _refresh_chip_label(self, name: str) -> None:
        chip = self._language_chips[name]
        installed = is_language_installed(name)
        chip.setText(name if installed else f"{name}  ⭳")

    def _on_ocr_toggled(self, checked: bool) -> None:
        self._settings.ocr_enabled = checked
        self._language_section.setVisible(checked)
        self.ocrSettingsChanged.emit()

    def _on_language_toggled(self, name: str) -> None:
        chip = self._language_chips[name]
        selected = chip.isChecked()

        if selected and not is_language_installed(name):
            chip.setEnabled(False)
            chip.setText(f"{name}  …")
            self._start_download(name)
        else:
            self._save_selected_languages()
            self.ocrSettingsChanged.emit()

    def _start_download(self, name: str) -> None:
        thread = QThread(self)
        worker = _LanguageDownloadWorker(name)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda n, ok: self._on_download_finished(n, ok, thread))
        worker.finished.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_download_finished(self, name: str, success: bool, thread: QThread) -> None:
        chip = self._language_chips[name]
        chip.setEnabled(True)
        if not success:
            chip.setChecked(False)
        self._refresh_chip_label(name)
        self._save_selected_languages()
        self.ocrSettingsChanged.emit()
        if thread in self._threads:
            self._threads.remove(thread)

    def _save_selected_languages(self) -> None:
        selected = [name for name, chip in self._language_chips.items() if chip.isChecked()]
        self._settings.ocr_languages = selected or list(self._language_chips.keys())[:1]

    def _on_theme_changed(self, label: str) -> None:
        theme = _THEME_LABELS[label]
        self._settings.theme = theme
        self.themeChanged.emit(theme)

    def _on_accent_selected(self, color: str) -> None:
        self._settings.accent_color = color
        self.accentChanged.emit(color)
