from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QStackedWidget,
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
from scanner_app.ui import icons
from scanner_app.ui.widgets.segmented_control import SegmentedControl
from scanner_app.ui.widgets.spinner import Spinner
from scanner_app.ui.widgets.toggle_switch import ToggleSwitch
from scanner_app.ui.widgets.wide_combo_box import WideComboBox

_RESOLUTIONS = [75, 150, 300, 600, 1200]
_DEFAULT_RESOLUTION = 300
_RESOLUTION_HINTS = {
    300: "Standard für A4/Letter-Dokumente",
    600: "Empfohlen für Fotos und kleine Vorlagen",
}
_SOURCE_LABELS = {"Automatisch": ScanSource.AUTO, "Flachbett": ScanSource.FLATBED, "Einzug": ScanSource.FEEDER}
_FILETYPE_LABELS = {
    "JPG": DocumentType.JPG,
    "PNG": DocumentType.PNG,
    "PDF": DocumentType.PDF,
    "TIF": DocumentType.TIF,
    "BMP": DocumentType.BMP,
}


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "sectionLabel")
    return label


_SCAN_ROW_IDLE = 0
_SCAN_ROW_ACTIVE = 1


class SettingsPanel(QWidget):
    scanRequested = Signal()
    scanAndRestartRequested = Signal()
    cancelScanRequested = Signal()
    deviceChanged = Signal()
    filetypeChanged = Signal(str)

    def __init__(
        self, backend: ScannerBackend, settings: AppSettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("leftPanel")
        self.setFixedWidth(380)
        self._backend = backend
        self._settings = settings
        self._devices: list[ScannerDevice] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        layout.addWidget(self._build_scanner_card())

        layout.addWidget(_section_label("QUELLE"))
        self._source_control = SegmentedControl(list(_SOURCE_LABELS.keys()))
        layout.addWidget(self._source_control)

        doc_type_row = QHBoxLayout()
        doc_type_label = _section_label("DATEITYP")
        doc_type_row.addWidget(doc_type_label)
        doc_type_row.addStretch()
        self._filetype_combo = WideComboBox()
        self._filetype_combo.setFixedWidth(160)
        self._filetype_combo.addItems(list(_FILETYPE_LABELS.keys()))
        self._filetype_combo.setCurrentText("PDF")
        self._filetype_combo.currentTextChanged.connect(self.filetypeChanged)
        doc_type_row.addWidget(self._filetype_combo)
        layout.addLayout(doc_type_row)

        layout.addWidget(_section_label("FARBMODUS"))
        self._color_control = SegmentedControl(["Farbe", "Schwarz-Weiß"])
        layout.addWidget(self._color_control)

        layout.addWidget(_section_label("AUFLÖSUNG"))
        self._resolution_combo = WideComboBox()
        self._resolution_combo.addItems([f"{dpi} DPI" for dpi in _RESOLUTIONS])
        self._resolution_combo.setCurrentIndex(_RESOLUTIONS.index(_DEFAULT_RESOLUTION))
        self._resolution_combo.currentIndexChanged.connect(self._update_resolution_hint)
        layout.addWidget(self._resolution_combo)
        self._resolution_hint_label = QLabel()
        self._resolution_hint_label.setObjectName("resolutionHint")
        self._resolution_hint_label.setWordWrap(True)
        layout.addWidget(self._resolution_hint_label)
        self._update_resolution_hint()

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
        self._strength_value_label.setProperty("role", "sliderValue")
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

        # Steuerelemente, die während eines laufenden Scans gesperrt werden (Issue #7) —
        # verhindert, dass Einstellungen verändert werden, während das Gerät bereits mit den
        # zuvor gelesenen Optionen scannt.
        self._scan_lockable_controls: list[QWidget] = [
            self._device_combo,
            self._source_control,
            self._filetype_combo,
            self._color_control,
            self._resolution_combo,
            self._brightness_slider,
            self._contrast_slider,
            self._auto_enhance_toggle,
            self._strength_slider,
        ]

        self._scan_stack = QStackedWidget()
        self._scan_stack.addWidget(self._build_scan_idle_row())
        self._scan_stack.addWidget(self._build_scan_active_row())
        layout.addWidget(self._scan_stack)

        self.refresh_devices()

    def _build_scan_idle_row(self) -> QWidget:
        container = QWidget()
        scan_row = QHBoxLayout(container)
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.setSpacing(1)
        self._scan_button = QPushButton("Scannen")
        self._scan_button.setProperty("role", "primaryLeft")
        self._scan_button.clicked.connect(self.scanRequested)
        self._scan_menu_button = QPushButton()
        self._scan_menu_button.setProperty("role", "primaryRight")
        self._scan_menu_button.setIcon(icons.svg_icon(icons.CHEVRON_DOWN, "#ffffff", size=13))
        self._scan_menu_button.setFixedWidth(34)
        self._scan_menu_button.setToolTip("Weitere Scan-Optionen")
        self._scan_menu_button.clicked.connect(self._show_scan_menu)
        scan_row.addWidget(self._scan_button, stretch=1)
        scan_row.addWidget(self._scan_menu_button)
        return container

    def _build_scan_active_row(self) -> QWidget:
        container = QWidget()
        container.setObjectName("scanActiveRow")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._scan_spinner = Spinner(size=15, color="#ffffff")
        row.addWidget(self._scan_spinner)

        status_label = QLabel("Scan läuft…")
        status_label.setAccessibleName("Scan läuft")
        status_label.setStyleSheet("color: white; font-weight: 600;")
        row.addWidget(status_label, stretch=1)

        cancel_button = QPushButton("Abbrechen")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setStyleSheet(
            "background: rgba(255,255,255,.18); border: none; border-radius: 5px;"
            " color: white; padding: 6px 12px; font-size: 12px;"
        )
        cancel_button.clicked.connect(self.cancelScanRequested)
        row.addWidget(cancel_button)
        return container

    def set_scanning(self, scanning: bool) -> None:
        self._scan_stack.setCurrentIndex(_SCAN_ROW_ACTIVE if scanning else _SCAN_ROW_IDLE)
        if scanning:
            self._scan_spinner.start()
        else:
            self._scan_spinner.stop()
        for control in self._scan_lockable_controls:
            control.setEnabled(not scanning)

    def _show_scan_menu(self) -> None:
        # Bewusst ohne QAction.setShortcut(): Strg+Eingabe/Strg+N sind bereits als echte
        # QShortcuts auf dem Hauptfenster registriert (siehe MainWindow) — ein zusätzliches
        # Binding hier würde bei geöffnetem Menü zu Qts "Ambiguous shortcut"-Warnung führen.
        # Der Tab-getrennte Text rechts wird von Qt trotzdem als Shortcut-Hinweis dargestellt.
        menu = QMenu(self)
        menu.setObjectName("scanMenu")
        scan_action = menu.addAction("Scannen\tStrg+Eingabe")
        scan_action.triggered.connect(self.scanRequested)
        restart_action = menu.addAction("Scannen und neu beginnen\tStrg+N")
        restart_action.triggered.connect(self.scanAndRestartRequested)
        anchor = self._scan_menu_button.mapToGlobal(QPoint(0, 0))
        menu_height = menu.sizeHint().height()
        menu.exec(QPoint(anchor.x(), anchor.y() - menu_height - 4))

    def _build_scanner_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("scannerCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(icons.svg_icon(icons.SCANNER, self._settings.accent_color, size=20).pixmap(20, 20))
        icon_label.setFixedSize(20, 20)
        row.addWidget(icon_label)
        self._scanner_icon_label = icon_label

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        caption = QLabel("VERBUNDENER SCANNER")
        caption.setObjectName("scannerLabel")
        text_col.addWidget(caption)

        self._device_combo = WideComboBox()
        self._device_combo.setObjectName("scannerCombo")
        self._device_combo.currentIndexChanged.connect(lambda _i: self.deviceChanged.emit())
        text_col.addWidget(self._device_combo)
        row.addLayout(text_col, stretch=1)
        return card

    def _add_slider(self, layout: QVBoxLayout, label_text: str) -> QSlider:
        row = QHBoxLayout()
        row.addWidget(_section_label(label_text))
        row.addStretch()
        value_label = QLabel("0")
        value_label.setProperty("role", "sliderValue")
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

    def _update_resolution_hint(self, *_args) -> None:
        dpi = _RESOLUTIONS[self._resolution_combo.currentIndex()]
        hint = _RESOLUTION_HINTS.get(dpi, "")
        self._resolution_hint_label.setText(hint)
        self._resolution_hint_label.setVisible(bool(hint))

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
        if last_id and self._settings.auto_load_last_scanner:
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

    def apply_accent(self, accent: str) -> None:
        self._auto_enhance_toggle.set_accent(accent)
        self._scanner_icon_label.setPixmap(icons.svg_icon(icons.SCANNER, accent, size=20).pixmap(20, 20))
