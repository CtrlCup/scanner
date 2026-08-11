from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QMessageBox, QWidget

from scanner_app.app_settings import AppSettings
from scanner_app.backend import ScannerBackendError, get_backend
from scanner_app.models.document import Document, DocumentType, generate_filename
from scanner_app.ocr.ocr_engine import OcrError
from scanner_app.scanning_service import save_and_process
from scanner_app.ui.preview_panel import PreviewPanel
from scanner_app.ui.settings_dialog import SettingsDialog
from scanner_app.ui.settings_panel import SettingsPanel
from scanner_app.ui.theme import build_stylesheet, resolve_theme_mode


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scanner")
        self.resize(1180, 760)

        self.settings = AppSettings()
        self.backend = get_backend()
        self.document = Document(document_type=DocumentType.PDF)
        self._scan_tmp_dir = Path(tempfile.mkdtemp(prefix="scanner-app-"))

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.settings_panel = SettingsPanel(self.backend, self.settings)
        self.preview_panel = PreviewPanel()
        layout.addWidget(self.settings_panel)
        layout.addWidget(self.preview_panel, stretch=1)
        self.setCentralWidget(central)

        self.settings_panel.scanRequested.connect(self._on_scan_requested)
        self.settings_panel.addPageRequested.connect(self._on_add_page_requested)
        self.settings_panel.openSettingsRequested.connect(self._open_settings_dialog)
        self.settings_panel.deviceChanged.connect(self._on_device_changed)
        self.settings_panel.filetypeChanged.connect(lambda _t: self._update_add_page_enabled())

        self.preview_panel.deletePageRequested.connect(self._on_delete_page)
        self.preview_panel.pagesReordered.connect(self._on_pages_reordered)
        self.preview_panel.rotateRequested.connect(self._on_rotate_page)

        self._apply_theme()
        self._update_add_page_enabled()

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

        self.document.add_page(target)
        self._save_and_refresh()

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

    def _save_and_refresh(self) -> None:
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
            )
        except OcrError as exc:
            QMessageBox.warning(self, "OCR fehlgeschlagen", str(exc))

    def _current_output_path(self) -> Path:
        if self.document.output_path is None:
            filename = generate_filename(self.document.document_type)
            candidate = self.settings.save_directory / filename
            self.document.output_path = self._make_unique_path(candidate)
        return self.document.output_path

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

    # -- Einstellungen / Theme ----------------------------------------------------

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        dialog.accentChanged.connect(self._on_accent_changed)
        dialog.themeChanged.connect(lambda _t: self._apply_theme())
        dialog.exec()

    def _on_accent_changed(self, accent: str) -> None:
        self.settings_panel.apply_accent(accent)
        self._apply_theme()

    def _apply_theme(self) -> None:
        # Auf QApplication-Ebene gesetzt (nicht nur auf diesem Fenster), damit auch
        # eigenständige Top-Level-Dialoge (Einstellungen) zuverlässig mitgestylt werden.
        mode = resolve_theme_mode(self.settings.theme)
        stylesheet = build_stylesheet(mode, self.settings.accent_color)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
        else:
            self.setStyleSheet(stylesheet)

    def closeEvent(self, event) -> None:
        self.backend.close()
        super().closeEvent(event)
