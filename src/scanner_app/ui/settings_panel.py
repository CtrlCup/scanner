from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from scanner_app.app_settings import AppSettings
from scanner_app.backend.base import (
    ColorMode,
    ScannerBackend,
    ScannerDevice,
    ScanOptions,
    ScanSource,
)
from scanner_app.backend.exceptions import ScannerBackendError
from scanner_app.models.document import DocumentType
from scanner_app.ui.widgets.segmented_control import SegmentedControl
from scanner_app.ui.widgets.toggle_switch import ToggleSwitch

_RESOLUTIONS = [100, 150, 200, 300, 600]
_SOURCE_LABELS = {"Automatisch": ScanSource.AUTO, "Flachbett": ScanSource.FLATBED, "Einzug": ScanSource.FEEDER}
_FILETYPE_LABELS = {"PDF": DocumentType.PDF, "Bild": DocumentType.IMAGE}


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "sectionLabel")
    return label


class SettingsPanel(QWidget):
    scanRequested = Signal()
    addPageRequested = Signal()
    openSettingsRequested = Signal()
    deviceChanged = Signal()
    filetypeChanged = Signal(str)
    saveFolderChangeRequested = Signal()

    def __init__(
        self, backend: ScannerBackend, settings: AppSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")
        self.setFixedWidth(360)
        self._backend = backend
        self._settings = settings
        self._devices: list[ScannerDevice] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(lambda _i: self.deviceChanged.emit())
        layout.addWidget(_section_label("VERBUNDENER SCANNER"))
        layout.addWidget(self._device_combo)

        layout.addWidget(_section_label("QUELLE"))
        self._source_control = SegmentedControl(list(_SOURCE_LABELS.keys()))
        layout.addWidget(self._source_control)

        layout.addWidget(_section_label("DATEITYP"))
        self._filetype_combo = QComboBox()
        self._filetype_combo.addItems(list(_FILETYPE_LABELS.keys()))
        self._filetype_combo.currentTextChanged.connect(self.filetypeChanged)
        layout.addWidget(self._filetype_combo)

        layout.addWidget(_section_label("FARBMODUS"))
        self._color_control = SegmentedControl(["Farbe", "Schwarz-Weiß"])
        layout.addWidget(self._color_control)

        layout.addWidget(_section_label("AUFLÖSUNG"))
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems([f"{dpi} DPI" for dpi in _RESOLUTIONS])
        self._resolution_combo.setCurrentIndex(_RESOLUTIONS.index(300))
        layout.addWidget(self._resolution_combo)

        self._brightness_slider = self._add_slider(layout, "HELLIGKEIT")
        self._contrast_slider = self._add_slider(layout, "KONTRAST")

        enhance_row = QHBoxLayout()
        enhance_row.addWidget(_section_label("AUTOMATISCHE BILDKORREKTUR"))
        enhance_row.addStretch()
        self._auto_enhance_toggle = ToggleSwitch(accent=settings.accent_color)
        self._auto_enhance_toggle.setChecked(True)
        self._auto_enhance_toggle.toggled.connect(self._on_auto_enhance_toggled)
        enhance_row.addWidget(self._auto_enhance_toggle)
        layout.addLayout(enhance_row)

        strength_row = QHBoxLayout()
        strength_row.addWidget(_section_label("STÄRKE"))
        strength_row.addStretch()
        self._strength_value_label = QLabel("40%")
        strength_row.addWidget(self._strength_value_label)
        layout.addLayout(strength_row)
        self._strength_slider = QSlider(Qt.Orientation.Horizontal)
        self._strength_slider.setRange(0, 100)
        self._strength_slider.setValue(40)
        self._strength_slider.valueChanged.connect(
            lambda v: self._strength_value_label.setText(f"{v}%")
        )
        layout.addWidget(self._strength_slider)

        layout.addStretch()

        bottom_icons = QHBoxLayout()
        self._folder_button = QPushButton("📁")
        self._folder_button.setProperty("role", "icon")
        self._folder_button.setToolTip("Speicherpfad wählen / öffnen")
        self._folder_button.clicked.connect(self._choose_save_folder)
        self._settings_button = QPushButton("⚙")
        self._settings_button.setProperty("role", "icon")
        self._settings_button.setToolTip("Einstellungen")
        self._settings_button.clicked.connect(self.openSettingsRequested)
        bottom_icons.addWidget(self._folder_button)
        bottom_icons.addWidget(self._settings_button)
        bottom_icons.addStretch()
        layout.addLayout(bottom_icons)

        scan_row = QHBoxLayout()
        self._scan_button = QPushButton("Neue Seite scannen")
        self._scan_button.setProperty("role", "primary")
        self._scan_button.clicked.connect(self.scanRequested)
        self._add_page_button = QPushButton("+")
        self._add_page_button.setProperty("role", "primary")
        self._add_page_button.setFixedWidth(44)
        self._add_page_button.setEnabled(False)
        self._add_page_button.clicked.connect(self.addPageRequested)
        scan_row.addWidget(self._scan_button, stretch=1)
        scan_row.addWidget(self._add_page_button)
        layout.addLayout(scan_row)

        self.refresh_devices()

    def _add_slider(self, layout: QVBoxLayout, label_text: str) -> QSlider:
        row = QHBoxLayout()
        row.addWidget(_section_label(label_text))
        row.addStretch()
        value_label = QLabel("0")
        row.addWidget(value_label)
        layout.addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        layout.addWidget(slider)
        return slider

    def _on_auto_enhance_toggled(self, checked: bool) -> None:
        self._strength_slider.setEnabled(checked)

    def _choose_save_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Speicherpfad wählen", str(self._settings.save_directory)
        )
        if directory:
            self._settings.save_directory = directory
            self.saveFolderChangeRequested.emit()

    def refresh_devices(self) -> None:
        try:
            self._devices = self._backend.list_devices()
        except ScannerBackendError:
            self._devices = []

        self._device_combo.clear()
        if not self._devices:
            self._device_combo.addItem("Kein Scanner gefunden")
            self._device_combo.setEnabled(False)
            return
        self._device_combo.setEnabled(True)
        for device in self._devices:
            self._device_combo.addItem(device.display_name, userData=device.device_id)
        last_id = self._settings.last_device_id
        if last_id:
            index = self._device_combo.findData(last_id)
            if index >= 0:
                self._device_combo.setCurrentIndex(index)

    def current_device(self) -> ScannerDevice | None:
        index = self._device_combo.currentIndex()
        if index < 0 or index >= len(self._devices):
            return None
        return self._devices[index]

    def current_document_type(self) -> DocumentType:
        return _FILETYPE_LABELS[self._filetype_combo.currentText()]

    def current_scan_options(self) -> ScanOptions:
        return ScanOptions(
            source=_SOURCE_LABELS[self._source_control.current()],
            color_mode=ColorMode.COLOR if self._color_control.current() == "Farbe" else ColorMode.GRAYSCALE,
            resolution_dpi=_RESOLUTIONS[self._resolution_combo.currentIndex()],
            brightness=self._brightness_slider.value(),
            contrast=self._contrast_slider.value(),
            auto_enhance=self._auto_enhance_toggle.isChecked(),
            auto_enhance_strength=self._strength_slider.value(),
        )

    def set_can_add_page(self, enabled: bool) -> None:
        self._add_page_button.setEnabled(enabled)

    def apply_accent(self, accent: str) -> None:
        self._auto_enhance_toggle.set_accent(accent)
