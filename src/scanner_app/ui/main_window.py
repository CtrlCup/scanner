from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from scanner_app.app_settings import DEFAULT_FILENAME_PATTERN, AppSettings
from scanner_app.backend import ScannerBackendError, get_backend
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
        self.settings_panel.addPageRequested.connect(self._on_add_page_requested)
        self.settings_panel.deviceChanged.connect(self._on_device_changed)
        self.settings_panel.filetypeChanged.connect(lambda _t: self._update_add_page_enabled())

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
        self._update_add_page_enabled()
        self._icon_rail.set_save_path(str(self.settings.save_directory))

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
        # "Neue Seite scannen" startet laut Anforderung IMMER ein neues Dokument.
        filetype = self.settings_panel.current_document_type()
        self.document = Document(document_type=filetype)
        self._scan_and_append()

    def _on_add_page_requested(self) -> None:
        if not self.document.can_add_page:
            return
        self._scan_and_append()

    def _scan_and_append(self) -> None:
        device = self.settings_panel.current_device()
        if device is None:
            QMessageBox.warning(self, "Kein Scanner", "Bitte zuerst einen Scanner auswählen.")
            return

        options = self.settings_panel.current_scan_options()
        target = self._scan_tmp_dir / f"{uuid.uuid4().hex}.png"
        try:
            self.backend.scan_page(device, options, target)
        except ScannerBackendError as exc:
            QMessageBox.critical(self, "Scan fehlgeschlagen", str(exc))
            return

        page = self.document.add_page(target)
        if self.settings.auto_rotate_enabled:
            rotation = detect_rotation(target)
            if rotation:
                self.document.rotate_page(page.id, rotation)
        self._save_and_refresh(notify=True)

    # -- Seiten verwalten ----------------------------------------------------------

    def _on_delete_page(self, page_id: str) -> None:
        self.document.remove_page(page_id)
        self._save_and_refresh()

    def _on_pages_reordered(self, ordered_ids: list[str]) -> None:
        by_id = {page.id: page for page in self.document.pages}
        self.document.pages = [by_id[pid] for pid in ordered_ids if pid in by_id]
        self._save_and_refresh()

    def _on_rotate_page(self, page_id: str, degrees: int) -> None:
        self.document.rotate_page(page_id, degrees)
        self._save_and_refresh()

    def _save_and_refresh(self, *, notify: bool = False) -> None:
        self.preview_panel.set_document(self.document)
        self._update_add_page_enabled()

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

    def _update_add_page_enabled(self) -> None:
        filetype = self.settings_panel.current_document_type()
        enabled = filetype is DocumentType.PDF and not self.document.is_empty
        self.settings_panel.set_can_add_page(enabled)

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
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update verfügbar")
        box.setText(f"Eine neue Version ist verfügbar: v{info.version}")
        if info.notes:
            box.setInformativeText(info.notes[:500])
        open_button = box.addButton("Release-Seite öffnen", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Später", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(info.html_url)

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
        self.settings_page.shutdown()
        self.backend.close()
        super().closeEvent(event)
