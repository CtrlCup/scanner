from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from scanner_app import windows_updater
from scanner_app.app_settings import DEFAULT_FILENAME_PATTERN, AppSettings
from scanner_app.backend import ScannerBackendError, get_backend
from scanner_app.backend.base import ScannerDevice, ScanOptions
from scanner_app.models.document import Document, DocumentType, generate_filename
from scanner_app.ocr.ocr_engine import OcrError
from scanner_app.ocr.orientation import detect_rotation
from scanner_app.resources import resource_path
from scanner_app.scanning_service import save_and_process
from scanner_app.ui.preview_panel import PreviewPanel
from scanner_app.ui.settings_page import SettingsPage
from scanner_app.ui.settings_panel import SettingsPanel
from scanner_app.ui.theme import build_stylesheet, palette_for, resolve_theme_mode
from scanner_app.ui.widgets.toast import Toast
from scanner_app.ui.widgets.window_chrome import IconRail, TitleBar

_PAGE_SCANNER = 0
_PAGE_SETTINGS = 1

_SHADOW_MARGIN = 24
_RESIZE_MARGIN = 6


class _ScanWorker(QObject):
    """Führt `ScannerBackend.scan_page()` in einem Hintergrund-Thread aus — dieser Aufruf
    blockiert je nach Backend (SANE/WIA) mehrere Sekunden, darf daher nie im UI-Thread
    laufen, sonst friert das ganze Fenster während des Scans ein (siehe Issue #7).
    """

    finished = Signal(Path)
    failed = Signal(str)

    def __init__(self, backend, device: ScannerDevice, options: ScanOptions, target: Path) -> None:
        super().__init__()
        self._backend = backend
        self._device = device
        self._options = options
        self._target = target

    def run(self) -> None:
        try:
            self._backend.scan_page(self._device, self._options, self._target)
        except ScannerBackendError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(self._target)


class _UpdateInstallWorker(QObject):
    """Lädt den geprüften Windows-Installer eines neueren Releases im Hintergrund herunter
    (siehe windows_updater.py) — Prüfsummen-Abruf und Download in einem Rutsch, damit für
    einen Update-Vorgang nur ein einziger Hintergrund-Thread nötig ist.
    """

    progress = Signal(int, int)
    succeeded = Signal(Path)
    failed = Signal(str)

    def __init__(self, installer_url: str, checksum_url: str) -> None:
        super().__init__()
        self._installer_url = installer_url
        self._checksum_url = checksum_url
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            checksum = windows_updater.fetch_checksum(self._checksum_url)
            if self._cancelled:
                self.failed.emit("Abgebrochen.")
                return
            path = windows_updater.download_installer(
                self._installer_url,
                checksum,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_check=lambda: self._cancelled,
            )
        except windows_updater.UpdateInstallError as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(path)


class _ResizableRoot(QWidget):
    """Äußerste Ebene des selbstgezeichneten Fensters: transparenter Rand, der Platz für
    den Schlagschatten lässt, und gleichzeitig die Greifzone für Rand-Resize per
    QWindow.startSystemResize() (funktioniert plattformübergreifend unter Windows/Linux,
    im Unterschied zu manueller Geometrie-Mathematik über mouseMoveEvent).
    """

    def __init__(self, window: QMainWindow) -> None:
        super().__init__()
        self.setObjectName("outerRoot")
        self._window = window
        self.setMouseTracking(True)

    def _edges_at(self, pos: QPoint) -> Qt.Edges:
        if self._window.isMaximized():
            return Qt.Edges()
        edges = Qt.Edges()
        if pos.x() <= _RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= self.width() - _RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= _RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= self.height() - _RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges: Qt.Edges) -> Qt.CursorShape:
        horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        diag_tlbr = (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or (
            edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge
        )
        diag_trbl = (edges & Qt.Edge.RightEdge and edges & Qt.Edge.TopEdge) or (
            edges & Qt.Edge.LeftEdge and edges & Qt.Edge.BottomEdge
        )
        if diag_tlbr:
            return Qt.CursorShape.SizeFDiagCursor
        if diag_trbl:
            return Qt.CursorShape.SizeBDiagCursor
        if horizontal:
            return Qt.CursorShape.SizeHorCursor
        if vertical:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mouseMoveEvent(self, event) -> None:
        edges = self._edges_at(event.position().toPoint())
        self.setCursor(self._cursor_for(edges))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._edges_at(event.position().toPoint())
            if edges:
                handle = self._window.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    event.accept()
                    return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Selbstgezeichnetes Fenster (eigene Titelleiste, Fensterknöpfe, abgerundete Ecken)
        # statt nativer Dekoration — bewusste Design-Entscheidung, damit die App auf
        # Windows und Linux exakt identisch aussieht (siehe CLAUDE.md).
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Scanner")
        self.setWindowIcon(QIcon(str(resource_path("icon.png"))))
        self.resize(1180 + 2 * _SHADOW_MARGIN, 780 + 2 * _SHADOW_MARGIN)
        self.setMinimumSize(900 + 2 * _SHADOW_MARGIN, 560 + 2 * _SHADOW_MARGIN)

        self.settings = AppSettings()
        self.backend = get_backend()
        self.document = Document(document_type=DocumentType.PDF)
        self._scan_tmp_dir = Path(tempfile.mkdtemp(prefix="scanner-app-"))
        self._scan_thread: QThread | None = None
        self._scan_worker: _ScanWorker | None = None
        self._scan_cancelled = False
        self._update_thread: QThread | None = None
        self._update_worker: _UpdateInstallWorker | None = None
        self._update_progress_dialog: QProgressDialog | None = None

        root = _ResizableRoot(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(_SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN)
        self._root_layout = root_layout

        self._window_frame = QWidget()
        self._window_frame.setObjectName("windowFrame")
        self._shadow = QGraphicsDropShadowEffect(self._window_frame)
        self._shadow.setBlurRadius(48)
        self._shadow.setOffset(0, 12)
        self._shadow.setColor(QColor(0, 0, 0, 130))
        self._window_frame.setGraphicsEffect(self._shadow)
        frame_layout = QVBoxLayout(self._window_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self._title_bar = TitleBar()
        self._title_bar.minimizeRequested.connect(self.showMinimized)
        self._title_bar.maximizeRequested.connect(self._toggle_maximize)
        self._title_bar.closeRequested.connect(self.close)
        frame_layout.addWidget(self._title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._icon_rail = IconRail()
        self._icon_rail.scanRequested.connect(self._on_scan_requested)
        self._icon_rail.openFolderRequested.connect(self._open_save_folder)
        self._icon_rail.settingsRequested.connect(self._show_settings_page)
        body_layout.addWidget(self._icon_rail)

        scanner_view = QWidget()
        scanner_layout = QHBoxLayout(scanner_view)
        scanner_layout.setContentsMargins(0, 0, 0, 0)
        scanner_layout.setSpacing(0)

        self.settings_panel = SettingsPanel(self.backend, self.settings)
        self.preview_panel = PreviewPanel()
        scanner_layout.addWidget(self.settings_panel)
        scanner_layout.addWidget(self.preview_panel, stretch=1)

        self.settings_page = SettingsPage(self.settings)

        self._stack = QStackedWidget()
        self._stack.addWidget(scanner_view)
        self._stack.addWidget(self.settings_page)
        body_layout.addWidget(self._stack, stretch=1)

        frame_layout.addWidget(body, stretch=1)
        root_layout.addWidget(self._window_frame)
        self.setCentralWidget(root)

        self._toast = Toast(self._window_frame)

        self.settings_panel.scanRequested.connect(self._on_scan_requested)
        self.settings_panel.scanAndRestartRequested.connect(self._on_scan_and_restart_requested)
        self.settings_panel.cancelScanRequested.connect(self._cancel_scan)
        self.settings_panel.deviceChanged.connect(self._on_device_changed)

        self.preview_panel.deletePageRequested.connect(self._on_delete_page)
        self.preview_panel.pagesReordered.connect(self._on_pages_reordered)
        self.preview_panel.rotateRequested.connect(self._on_rotate_page)

        self.settings_page.backRequested.connect(self._show_scanner_page)
        self.settings_page.accentChanged.connect(self._on_accent_changed)
        self.settings_page.themeChanged.connect(lambda _t: self._apply_theme())
        self.settings_page.updateAvailable.connect(self._on_update_available)
        self.settings_page.showThumbnailsChanged.connect(self.preview_panel.set_thumbnails_visible)
        self.settings_page.saveDirectoryChanged.connect(self._icon_rail.set_save_path)

        self.preview_panel.set_thumbnails_visible(self.settings.show_thumbnails)
        self.preview_panel.set_document(self.document)
        self._apply_theme()
        self._icon_rail.set_save_path(str(self.settings.save_directory))

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._on_scan_requested)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._on_scan_requested)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._on_scan_and_restart_requested)

        # Verzögert, damit der Start-Vorgang der App selbst nicht blockiert/verzögert wird.
        # Die Prüfung von auto_update_check_enabled erfolgt bewusst erst beim Timer-Feuern
        # (nicht schon hier beim Scheduling) — Aufrufer wie Tests, die die Einstellung direkt
        # nach der Konstruktion noch deaktivieren, verhindern damit zuverlässig einen echten
        # Netzwerkaufruf.
        QTimer.singleShot(1500, self._maybe_check_for_updates)

    def _maybe_check_for_updates(self) -> None:
        if self.settings.auto_update_check_enabled:
            self.settings_page.check_for_updates()

    # -- Fensterrahmen -------------------------------------------------------------

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_maximized_visuals()
        super().changeEvent(event)

    def _update_maximized_visuals(self) -> None:
        maximized = self.isMaximized()
        self._title_bar.set_maximized(maximized)
        self._window_frame.setProperty("maximized", "true" if maximized else "false")
        self._window_frame.style().unpolish(self._window_frame)
        self._window_frame.style().polish(self._window_frame)
        margin = 0 if maximized else _SHADOW_MARGIN
        self._root_layout.setContentsMargins(margin, margin, margin, margin)
        self._shadow.setEnabled(not maximized)

    # -- Scannen -----------------------------------------------------------------

    def _on_scan_requested(self) -> None:
        """'Scannen': hängt an das aktuelle Dokument an oder beginnt neu, je nach
        `scan_default_mode`-Einstellung — siehe `_perform_scan`.
        """
        self._perform_scan(restart=False)

    def _on_scan_and_restart_requested(self) -> None:
        """'Scannen und neu beginnen': verwirft das aktuelle Dokument immer, unabhängig von
        `scan_default_mode`.
        """
        self._perform_scan(restart=True)

    def _perform_scan(self, *, restart: bool) -> None:
        if self._scan_thread is not None:
            return  # Ein Scan läuft bereits — Doppelklicks/Shortcut-Wiederholung ignorieren.

        filetype = self.settings_panel.current_document_type()
        start_new = (
            restart
            or self.document.document_type is not filetype
            or self.settings.scan_default_mode == "new"
            or not self.document.can_add_page
        )
        if start_new:
            self.document = Document(document_type=filetype)
        self._start_scan()

    def _start_scan(self) -> None:
        device = self.settings_panel.current_device()
        if device is None:
            QMessageBox.warning(self, "Kein Scanner", "Bitte zuerst einen Scanner auswählen.")
            return

        options = self.settings_panel.current_scan_options()
        target = self._scan_tmp_dir / f"{uuid.uuid4().hex}.png"

        self._scan_cancelled = False
        self.settings_panel.set_scanning(True)

        thread = QThread(self)
        worker = _ScanWorker(self.backend, device, options, target)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_scan_finished, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_scan_failed, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_scan_thread_finished)

        self._scan_thread = thread
        self._scan_worker = worker  # Referenz halten, sonst könnte der Worker vorzeitig gc'et werden.
        thread.start()

    def _on_scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None

    def _on_scan_finished(self, target: Path) -> None:
        self.settings_panel.set_scanning(False)
        if self._scan_cancelled:
            return  # Nutzer hat währenddessen abgebrochen — Ergebnis verwerfen.

        page = self.document.add_page(target)
        if self.settings.auto_rotate_enabled:
            rotation = detect_rotation(target)
            if rotation:
                self.document.rotate_page(page.id, rotation)
        self._save_and_refresh(notify=True)

    def _on_scan_failed(self, message: str) -> None:
        self.settings_panel.set_scanning(False)
        if self._scan_cancelled:
            return
        QMessageBox.critical(self, "Scan fehlgeschlagen", message)

    def _cancel_scan(self) -> None:
        """Echte Scanner-Backends (SANE/WIA) lassen sich nicht sauber mitten im laufenden
        Aufruf unterbrechen — 'Abbrechen' markiert das kommende Ergebnis daher nur als zu
        verwerfen und gibt die UI sofort wieder frei, statt den Hintergrund-Thread hart zu
        beenden (das könnte den Scanner-Treiber in einem inkonsistenten Zustand zurücklassen).
        """
        self._scan_cancelled = True
        self.settings_panel.set_scanning(False)

    # -- Seiten verwalten ----------------------------------------------------------

    def _on_delete_page(self, page_id: str) -> None:
        self.document.remove_page(page_id)
        self._save_and_refresh(notify=True)

    def _on_pages_reordered(self, ordered_ids: list[str]) -> None:
        by_id = {page.id: page for page in self.document.pages}
        self.document.pages = [by_id[pid] for pid in ordered_ids if pid in by_id]
        self._save_and_refresh(notify=True)

    def _on_rotate_page(self, page_id: str, degrees: int) -> None:
        self.document.rotate_page(page_id, degrees)
        self._save_and_refresh(notify=True)

    def _save_and_refresh(self, *, notify: bool = False) -> None:
        self.preview_panel.set_document(self.document)

        if self.document.is_empty:
            return

        output_path = self._current_output_path()
        try:
            save_and_process(
                self.document,
                output_path,
                ocr_enabled=self.settings.ocr_enabled,
                ocr_languages=self.settings.ocr_languages,
                handwriting_enabled=self.settings.handwriting_enabled,
            )
        except OcrError as exc:
            QMessageBox.warning(self, "OCR fehlgeschlagen", str(exc))
            return

        if notify and self.settings.notify_on_finish:
            self._toast.show_message(f"Gespeichert: {output_path.name}")

    def _current_output_path(self) -> Path:
        if self.document.output_path is None:
            target_dir = self.settings.save_directory
            pattern = self._effective_filename_pattern()
            if "{Nummer}" in pattern:
                candidate = self._first_free_path(target_dir, pattern)
            else:
                filename = generate_filename(self.document.document_type, pattern=pattern)
                candidate = self._make_unique_path(target_dir / filename)
            self.document.output_path = candidate
        return self.document.output_path

    def _first_free_path(self, target_dir: Path, pattern: str) -> Path:
        sequence = 1
        while sequence < 10_000:
            filename = generate_filename(self.document.document_type, pattern=pattern, sequence=sequence)
            candidate = target_dir / filename
            if not candidate.exists():
                return candidate
            sequence += 1
        # Praktisch unerreichbar (10.000 Dateien mit demselben Muster im selben Ordner) —
        # als letzte Sicherheit trotzdem eindeutig statt eine Endlosschleife zu riskieren.
        filename = generate_filename(self.document.document_type, pattern=pattern, sequence=sequence)
        return self._make_unique_path(target_dir / filename)

    def _effective_filename_pattern(self) -> str:
        pattern = self.settings.default_filename_pattern
        try:
            pattern.format(Datum="x", Nummer="001")
        except (KeyError, IndexError, ValueError):
            return DEFAULT_FILENAME_PATTERN
        return pattern

    @staticmethod
    def _make_unique_path(path: Path) -> Path:
        """Hängt bei Kollision (z.B. zwei Scans in derselben Sekunde) ' (2)', ' (3)', ...
        an, statt ein bereits existierendes, anderes Dokument stillschweigend zu überschreiben.
        """
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _on_device_changed(self) -> None:
        device = self.settings_panel.current_device()
        if device is not None:
            self.settings.last_device_id = device.device_id

    # -- Speicherort öffnen ---------------------------------------------------------

    def _open_save_folder(self) -> None:
        path = self.settings.save_directory
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self._toast.show_message(f"Geöffnet: {path}")

    # -- Einstellungen / Theme ----------------------------------------------------

    def _show_settings_page(self) -> None:
        self._stack.setCurrentIndex(_PAGE_SETTINGS)

    def _show_scanner_page(self) -> None:
        self._stack.setCurrentIndex(_PAGE_SCANNER)
        self._icon_rail.set_save_path(str(self.settings.save_directory))

    def _on_accent_changed(self, accent: str) -> None:
        self.settings_panel.apply_accent(accent)
        self._apply_theme()

    def _on_update_available(self, info) -> None:
        # Automatische Installation nur, wenn diese Version über den Windows-Installer
        # installiert wurde (nicht die portable .exe, nicht ein Start aus dem Quellcode) UND
        # das Release sowohl einen Installer als auch dessen Prüfsumme als Asset mitbringt
        # (siehe update_checker.py) — sonst bleibt es beim reinen Hinweis-Dialog.
        can_auto_install = (
            windows_updater.is_installed_windows_build()
            and info.windows_installer_url
            and info.windows_installer_checksum_url
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update verfügbar")
        box.setText(f"Eine neue Version ist verfügbar: v{info.version}")
        if info.notes:
            box.setInformativeText(info.notes[:500])
        install_button = None
        if can_auto_install:
            install_button = box.addButton("Jetzt installieren", QMessageBox.ButtonRole.AcceptRole)
        open_button = box.addButton("Release-Seite öffnen", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Später", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if install_button is not None and clicked is install_button:
            self._start_auto_update(info)
        elif clicked is open_button:
            QDesktopServices.openUrl(info.html_url)

    def _start_auto_update(self, info) -> None:
        progress = QProgressDialog("Update wird heruntergeladen…", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("Update wird installiert")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        thread = QThread(self)
        worker = _UpdateInstallWorker(info.windows_installer_url, info.windows_installer_checksum_url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_update_progress, Qt.ConnectionType.QueuedConnection)
        worker.succeeded.connect(self._on_update_downloaded, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_update_download_failed, Qt.ConnectionType.QueuedConnection)
        worker.succeeded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_update_thread_finished)
        progress.canceled.connect(worker.cancel)

        self._update_thread = thread
        self._update_worker = worker
        self._update_progress_dialog = progress
        thread.start()

    def _on_update_thread_finished(self) -> None:
        self._update_thread = None
        self._update_worker = None

    def _on_update_progress(self, done: int, total: int) -> None:
        if self._update_progress_dialog is None:
            return
        if total:
            self._update_progress_dialog.setMaximum(total)
            self._update_progress_dialog.setValue(done)
        else:
            self._update_progress_dialog.setMaximum(0)  # unbekannte Größe -> unbestimmter Balken

    def _on_update_downloaded(self, installer_path: Path) -> None:
        if self._update_progress_dialog is not None:
            self._update_progress_dialog.close()
            self._update_progress_dialog = None
        try:
            windows_updater.launch_silent_install(installer_path)
        except windows_updater.UpdateInstallError as exc:
            QMessageBox.critical(self, "Update fehlgeschlagen", str(exc))
            return
        # Der Installer schließt die laufende Scanner.exe selbst über den Windows-Restart-
        # Manager (siehe packaging/scanner.iss) — die App beendet sich hier trotzdem bereits
        # selbst geordnet (Backend schließen, Hintergrund-Threads sauber beenden), statt sich
        # zwangsweise beenden zu lassen.
        self.close()

    def _on_update_download_failed(self, message: str) -> None:
        if self._update_progress_dialog is not None:
            self._update_progress_dialog.close()
            self._update_progress_dialog = None
        if "abgebrochen" not in message.lower():
            QMessageBox.warning(self, "Update fehlgeschlagen", message)

    def _apply_theme(self) -> None:
        # Auf QApplication-Ebene gesetzt (nicht nur auf diesem Fenster), damit auch
        # eigenständige Top-Level-Fenster (z.B. QMessageBox) zuverlässig mitgestylt werden.
        mode = resolve_theme_mode(self.settings.theme)
        accent = self.settings.accent_color
        stylesheet = build_stylesheet(mode, accent)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet(stylesheet)

        palette = palette_for(mode)
        self._title_bar.apply_colors(accent, palette["text_primary"], palette["winbtn_color"])
        self._icon_rail.apply_colors(accent, palette["rail_icon"])

    def closeEvent(self, event) -> None:
        # Qt darf einen QThread nie zerstören, während sein Worker noch läuft (harter Absturz
        # statt nur einer Warnung, siehe CLAUDE.md) — bei einem noch laufenden Scan also erst
        # auf dessen Ende warten, bevor das Fenster (und mit ihm dieser QThread) verschwindet.
        if self._scan_thread is not None:
            self._scan_thread.quit()
            self._scan_thread.wait(5000)
        if self._update_thread is not None:
            self._update_thread.quit()
            self._update_thread.wait(5000)
        self.settings_page.shutdown()
        self.backend.close()
        super().closeEvent(event)
