from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
from scanner_app.ocr.orientation import ensure_osd_installed
from scanner_app.ui import icons
from scanner_app.ui.widgets.segmented_control import SegmentedControl
from scanner_app.ui.widgets.toggle_switch import ToggleSwitch
from scanner_app.update_checker import UpdateInfo, check_for_update

_THEME_LABELS = {"Hell": "light", "Dunkel": "dark", "Automatisch": "system"}
_THEME_LABELS_REVERSE = {v: k for k, v in _THEME_LABELS.items()}
_GITHUB_URL = "https://github.com/CtrlCup/scanner"


class _TaskWorker(QObject):
    """Führt einen blockierenden Zero-Arg-Callable (z.B. Sprachpaket-/OSD-Download) in
    einem Hintergrund-Thread aus und meldet Erfolg/Misserfolg zurück an den UI-Thread.
    """

    finished = Signal(bool)

    def __init__(self, task: Callable[[], object]) -> None:
        super().__init__()
        self._task = task

    def run(self) -> None:
        try:
            self._task()
            self.finished.emit(True)
        except Exception:  # noqa: BLE001 - jeder Download-Fehler zählt als Fehlschlag
            self.finished.emit(False)


class _UpdateCheckWorker(QObject):
    """check_for_update() schlägt selbst nie fehlt (gibt bei Netzwerkfehlern None zurück) —
    dieser Worker trägt daher ein echtes Ergebnis (UpdateInfo | None), keinen bool-Erfolg.
    """

    finished = Signal(object)

    def __init__(self, current_version: str) -> None:
        super().__init__()
        self._current_version = current_version

    def run(self) -> None:
        self.finished.emit(check_for_update(self._current_version))


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "sectionLabel")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("settingsDivider")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


class SettingsPage(QWidget):
    """Eingebettete Einstellungen-Seite (kein separates Fenster), Struktur/Optik gemäß dem
    vorgegebenen Design-Mockup: Erscheinungsbild, Standard-Speicherort, Standard-Dateinamens-
    muster, Toggle-Gruppe (Scanner beim Start laden, Miniaturansichten, Benachrichtigung,
    automatisches Drehen, OCR an/aus + Sprachauswahl + optionale Handschrift-Erkennung),
    zusätzlich Akzentfarbe und Update-Check (im Mockup nicht enthalten, aber reale
    App-Funktionalität). Über backRequested navigiert das Hauptfenster zurück zur
    Scanner-Ansicht.
    """

    backRequested = Signal()
    accentChanged = Signal(str)
    themeChanged = Signal(str)
    ocrSettingsChanged = Signal()
    showThumbnailsChanged = Signal(bool)
    saveDirectoryChanged = Signal(str)
    updateAvailable = Signal(object)  # UpdateInfo, emitted wenn eine neue Version gefunden wird

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._settings = settings
        self._threads: list[QThread] = []
        self._language_chips: dict[str, QPushButton] = {}
        self._pending_update: UpdateInfo | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("settingsHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(16, 0, 20, 0)
        header.setFixedHeight(56)
        back_button = QPushButton()
        back_button.setObjectName("railIconButton")
        back_button.setIcon(icons.svg_icon(icons.BACK_ARROW, "#8a8a8a", size=16))
        back_button.setFixedSize(30, 30)
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.clicked.connect(self.backRequested)
        header_row.addWidget(back_button)
        header_row.addSpacing(6)
        header_label = QLabel("Einstellungen")
        header_label.setObjectName("settingsHeaderLabel")
        header_row.addWidget(header_label)
        header_row.addStretch()
        outer_layout.addWidget(header)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("settingsScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll_area)

        # Als eingebettete Seite steht deutlich mehr Breite zur Verfügung als im früheren
        # Dialog — Inhalt bleibt auf eine lesbare Breite begrenzt und zentriert, statt jede
        # Zeile über die volle Fensterbreite zu strecken.
        centering_wrapper = QWidget()
        centering_layout = QHBoxLayout(centering_wrapper)
        centering_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidget(centering_wrapper)

        content = QWidget()
        content.setMaximumWidth(520)
        centering_layout.addStretch()
        centering_layout.addWidget(content)
        centering_layout.addStretch()

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # -- Erscheinungsbild ---------------------------------------------------------
        layout.addWidget(_section_label("ERSCHEINUNGSBILD"))
        self._theme_control = SegmentedControl(list(_THEME_LABELS.keys()))
        self._theme_control.set_current(_THEME_LABELS_REVERSE.get(settings.theme, "Automatisch"))
        self._theme_control.currentChanged.connect(self._on_theme_changed)
        layout.addWidget(self._theme_control)

        accent_label = QLabel("AKZENTFARBE")
        accent_label.setProperty("role", "sectionLabel")
        layout.addWidget(accent_label)
        accent_row = QHBoxLayout()
        self._accent_swatches: dict[str, QPushButton] = {}
        for color in ACCENT_SWATCHES:
            swatch = QPushButton()
            swatch.setFixedSize(26, 26)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.clicked.connect(lambda _checked, c=color: self._on_accent_selected(c))
            self._accent_swatches[color] = swatch
            accent_row.addWidget(swatch)
        accent_row.addStretch()
        layout.addLayout(accent_row)
        self._refresh_accent_swatches()

        layout.addWidget(_divider())

        # -- Standard-Speicherort -------------------------------------------------------
        layout.addWidget(_section_label("STANDARD-SPEICHERORT"))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._save_path_edit = QLineEdit(str(settings.save_directory))
        self._save_path_edit.setReadOnly(True)
        path_row.addWidget(self._save_path_edit, stretch=1)
        browse_button = QPushButton("Durchsuchen…")
        browse_button.setProperty("role", "secondary")
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_button.clicked.connect(self._on_browse_save_directory)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        # -- Standard-Dateinamensmuster --------------------------------------------------
        layout.addWidget(_section_label("STANDARD-DATEINAMENSMUSTER"))
        self._filename_pattern_edit = QLineEdit(settings.default_filename_pattern)
        self._filename_pattern_edit.textChanged.connect(self._on_filename_pattern_changed)
        layout.addWidget(self._filename_pattern_edit)
        pattern_hint = QLabel("Platzhalter: {Datum}, {Nummer}")
        pattern_hint.setProperty("role", "hint")
        layout.addWidget(pattern_hint)

        layout.addWidget(_divider())

        # -- Toggle-Gruppe ----------------------------------------------------------------
        self._auto_load_toggle = self._add_toggle_row(
            layout, "Zuletzt verwendeten Scanner beim Start laden", settings.auto_load_last_scanner
        )
        self._auto_load_toggle.toggled.connect(self._on_auto_load_toggled)

        self._show_thumbs_toggle = self._add_toggle_row(
            layout, "Miniaturansichten in der Vorschau anzeigen", settings.show_thumbnails
        )
        self._show_thumbs_toggle.toggled.connect(self._on_show_thumbnails_toggled)

        self._notify_toggle = self._add_toggle_row(
            layout, "Benachrichtigung nach Fertigstellung", settings.notify_on_finish
        )
        self._notify_toggle.toggled.connect(self._on_notify_toggled)

        self._auto_rotate_toggle = self._add_toggle_row(
            layout, "Dokument automatisch drehen", settings.auto_rotate_enabled
        )
        self._auto_rotate_toggle.toggled.connect(self._on_auto_rotate_toggled)

        self._ocr_toggle = self._add_toggle_row(
            layout, "OCR (Texterkennung) aktivieren", settings.ocr_enabled
        )
        self._ocr_toggle.toggled.connect(self._on_ocr_toggled)

        self._language_section = QWidget()
        language_layout = QVBoxLayout(self._language_section)
        language_layout.setContentsMargins(0, 10, 0, 0)
        language_layout.setSpacing(10)
        language_layout.addWidget(_divider())

        self._handwriting_toggle = self._add_toggle_row(
            language_layout, "Handschrift-Erkennung", settings.handwriting_enabled
        )
        self._handwriting_toggle.toggled.connect(self._on_handwriting_toggled)

        language_hint = QLabel("Primärsprachen (werden bei Bedarf heruntergeladen)")
        language_hint.setProperty("role", "sectionLabel")
        language_layout.addWidget(language_hint)

        chip_grid = QGridLayout()
        chip_grid.setSpacing(8)
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

        layout.addWidget(_divider())

        # -- Updates ------------------------------------------------------------------------
        auto_update_row = QHBoxLayout()
        auto_update_label = QLabel("Automatisch nach Updates suchen")
        auto_update_label.setProperty("role", "sectionLabel")
        auto_update_row.addWidget(auto_update_label)
        auto_update_row.addStretch()
        self._auto_update_toggle = ToggleSwitch(accent=settings.accent_color)
        self._auto_update_toggle.setChecked(settings.auto_update_check_enabled)
        self._auto_update_toggle.toggled.connect(self._on_auto_update_toggled)
        auto_update_row.addWidget(self._auto_update_toggle)
        layout.addLayout(auto_update_row)

        update_row = QHBoxLayout()
        self._update_status_label = QLabel(f"Version {__version__}")
        self._update_status_label.setProperty("role", "hint")
        update_row.addWidget(self._update_status_label)
        update_row.addStretch()
        self._check_update_button = QPushButton("Jetzt prüfen")
        self._check_update_button.setProperty("role", "secondary")
        self._check_update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_update_button.clicked.connect(self._on_check_updates_clicked)
        update_row.addWidget(self._check_update_button)
        layout.addLayout(update_row)

        self._download_update_button = QPushButton("Neue Version öffnen")
        self._download_update_button.setProperty("role", "primary")
        self._download_update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_update_button.setVisible(False)
        self._download_update_button.clicked.connect(self._on_open_update_clicked)
        layout.addWidget(self._download_update_button)

        layout.addWidget(_divider())

        footer = QLabel(f"Mit <span style='color:#e0304a'>❤</span> von Alex entwickelt · v{__version__}")
        footer.setObjectName("footerCredit")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        github_link = QLabel(f'<a href="{_GITHUB_URL}">GitHub-Projekt ansehen</a>')
        github_link.setObjectName("footerLink")
        github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github_link.setOpenExternalLinks(False)
        github_link.linkActivated.connect(lambda url: QDesktopServices.openUrl(url))
        layout.addWidget(github_link)

        # Als Seite steht mehr Höhe zur Verfügung als im früheren Dialog — überschüssiger
        # Platz soll hier unten landen, statt dass Qt ihn auf alle Zeilen verteilt (was sie
        # unnötig aufbläht und die leicht abweichende Hintergrundfarbe einzelner Labels
        # sichtbar macht).
        layout.addStretch()

    def _add_toggle_row(self, layout: QVBoxLayout, label_text: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        label = QLabel(label_text)
        row.addWidget(label)
        row.addStretch()
        toggle = ToggleSwitch(accent=self._settings.accent_color)
        toggle.setChecked(checked)
        row.addWidget(toggle)
        layout.addLayout(row)
        return toggle

    # -- Standard-Speicherort ---------------------------------------------------------

    def _on_browse_save_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Speicherpfad wählen", str(self._settings.save_directory)
        )
        if directory:
            self._settings.save_directory = directory
            self._save_path_edit.setText(directory)
            self.saveDirectoryChanged.emit(directory)

    def _on_filename_pattern_changed(self, text: str) -> None:
        self._settings.default_filename_pattern = text

    # -- Toggle-Gruppe ------------------------------------------------------------------

    def _on_auto_load_toggled(self, checked: bool) -> None:
        self._settings.auto_load_last_scanner = checked

    def _on_show_thumbnails_toggled(self, checked: bool) -> None:
        self._settings.show_thumbnails = checked
        self.showThumbnailsChanged.emit(checked)

    def _on_notify_toggled(self, checked: bool) -> None:
        self._settings.notify_on_finish = checked

    # -- Automatisches Drehen -------------------------------------------------------

    def _on_auto_rotate_toggled(self, checked: bool) -> None:
        self._settings.auto_rotate_enabled = checked
        if checked:
            self._auto_rotate_toggle.setEnabled(False)
            self._run_in_background(ensure_osd_installed, self._on_osd_ready)

    def _on_osd_ready(self, success: bool) -> None:
        self._auto_rotate_toggle.setEnabled(True)
        if not success:
            self._auto_rotate_toggle.setChecked(False)
            self._settings.auto_rotate_enabled = False

    # -- OCR / Sprachen / Handschrift ------------------------------------------------

    def _refresh_chip_label(self, name: str) -> None:
        chip = self._language_chips[name]
        installed = is_language_installed(name)
        chip.setText(name if installed else f"{name}  ↓")

    def _on_ocr_toggled(self, checked: bool) -> None:
        self._settings.ocr_enabled = checked
        self._language_section.setVisible(checked)
        self.ocrSettingsChanged.emit()

    def _on_handwriting_toggled(self, checked: bool) -> None:
        self._settings.handwriting_enabled = checked
        self.ocrSettingsChanged.emit()

    def _on_language_toggled(self, name: str) -> None:
        chip = self._language_chips[name]
        selected = chip.isChecked()

        if selected and not is_language_installed(name):
            chip.setEnabled(False)
            chip.setText(f"{name}  …")
            self._run_in_background(
                lambda: download_language(name), lambda ok: self._on_language_ready(name, ok)
            )
        else:
            self._save_selected_languages()
            self.ocrSettingsChanged.emit()

    def _on_language_ready(self, name: str, success: bool) -> None:
        chip = self._language_chips[name]
        chip.setEnabled(True)
        if not success:
            chip.setChecked(False)
        self._refresh_chip_label(name)
        self._save_selected_languages()
        self.ocrSettingsChanged.emit()

    def _save_selected_languages(self) -> None:
        selected = [name for name, chip in self._language_chips.items() if chip.isChecked()]
        self._settings.ocr_languages = selected or list(self._language_chips.keys())[:1]

    # -- Hintergrund-Downloads --------------------------------------------------------

    def _run_in_background(self, task: Callable[[], object], on_done: Callable[[bool], None]) -> None:
        thread = QThread(self)
        worker = _TaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _handle_finished(success: bool) -> None:
            on_done(success)
            if thread in self._threads:
                self._threads.remove(thread)

        # QueuedConnection erzwungen: eine Verbindung zu einer freien Python-Closure (statt
        # einer QObject-gebundenen Methode) lässt Qt die Empfänger-Thread-Zugehörigkeit nicht
        # zuverlässig erkennen und würde sonst teils direkt im Hintergrund-Thread ausgeführt —
        # UI-Widgets dürfen aber nur im GUI-Thread angefasst werden.
        worker.finished.connect(_handle_finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    # -- Darstellung ------------------------------------------------------------------

    def _on_theme_changed(self, label: str) -> None:
        theme = _THEME_LABELS[label]
        self._settings.theme = theme
        self.themeChanged.emit(theme)

    def _refresh_accent_swatches(self) -> None:
        current = self._settings.accent_color
        for color, swatch in self._accent_swatches.items():
            border = "white" if color == current else "transparent"
            swatch.setStyleSheet(
                f"background-color: {color}; border-radius: 13px; "
                f"border: 2px solid {border};"
            )

    def _on_accent_selected(self, color: str) -> None:
        self._settings.accent_color = color
        self._refresh_accent_swatches()
        self.accentChanged.emit(color)

    # -- Updates ------------------------------------------------------------------------

    def _on_auto_update_toggled(self, checked: bool) -> None:
        self._settings.auto_update_check_enabled = checked

    def _on_check_updates_clicked(self) -> None:
        self.check_for_updates()

    def check_for_updates(self) -> None:
        """Öffentlich, damit z.B. MainWindow beim Start automatisch prüfen kann —
        aktualisiert in jedem Fall das eigene Status-Label, emittiert updateAvailable
        zusätzlich nur bei einem echten Fund.
        """
        self._check_update_button.setEnabled(False)
        self._update_status_label.setText("Suche nach Updates …")
        self._start_update_check()

    def _start_update_check(self) -> None:
        thread = QThread(self)
        worker = _UpdateCheckWorker(__version__)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _handle_finished(result: UpdateInfo | None) -> None:
            self._on_update_checked(result)
            if thread in self._threads:
                self._threads.remove(thread)

        worker.finished.connect(_handle_finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_update_checked(self, info: UpdateInfo | None) -> None:
        self._check_update_button.setEnabled(True)
        self._pending_update = info
        if info is None:
            self._update_status_label.setText(f"Version {__version__} — aktuell")
            self._download_update_button.setVisible(False)
            return
        self._update_status_label.setText(f"Version {__version__} — Update auf v{info.version} verfügbar")
        self._download_update_button.setVisible(True)
        self.updateAvailable.emit(info)

    # -- Aufräumen ------------------------------------------------------------------------

    def shutdown(self) -> None:
        """Wartet auf alle noch laufenden Hintergrund-Threads (Sprachpaket-/OSD-Download,
        Update-Check). Vor dem Schließen der Seite/App aufrufen — Qt darf einen QThread nie
        zerstören, während sein Worker noch läuft (führt zu einem harten Absturz, nicht nur
        zu einer Warnung, siehe CLAUDE.md).
        """
        for thread in list(self._threads):
            thread.quit()
            thread.wait(3000)

    def _on_open_update_clicked(self) -> None:
        if self._pending_update is not None:
            QDesktopServices.openUrl(self._pending_update.html_url)
