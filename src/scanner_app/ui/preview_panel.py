from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scanner_app.models.document import Document
from scanner_app.ui.widgets.thumbnail_strip import ThumbnailStrip

_EMPTY_TEXT = "Noch keine Seite gescannt"


class PreviewPanel(QWidget):
    """Rechte Seite: große Vorschau der fokussierten Seite, Rotieren-Buttons darüber,
    Thumbnail-Leiste aller Seiten darunter (Löschen per ×, Neuordnen per Drag&Drop).
    """

    rotateRequested = Signal(str, int)  # page_id, delta_degrees
    deletePageRequested = Signal(str)
    pagesReordered = Signal(list)
    pageSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self._selected_page_id: str | None = None
        self._current_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Vorschau")
        title.setProperty("role", "sectionLabel")
        header.addWidget(title)
        header.addStretch()

        self._rotate_left_btn = QPushButton("⟲")
        self._rotate_right_btn = QPushButton("⟳")
        for button, tooltip in (
            (self._rotate_left_btn, "Seite nach links drehen"),
            (self._rotate_right_btn, "Seite nach rechts drehen"),
        ):
            button.setProperty("role", "icon")
            button.setToolTip(tooltip)
            button.setEnabled(False)
            header.addWidget(button)
        layout.addLayout(header)

        self._preview_label = QLabel(_EMPTY_TEXT)
        self._preview_label.setObjectName("previewArea")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(300)
        layout.addWidget(self._preview_label, stretch=1)

        self._thumb_strip = ThumbnailStrip()
        layout.addWidget(self._thumb_strip)

        self._rotate_left_btn.clicked.connect(lambda: self._request_rotate(-90))
        self._rotate_right_btn.clicked.connect(lambda: self._request_rotate(90))
        self._thumb_strip.pageSelected.connect(self._on_page_selected)
        self._thumb_strip.pageDeleteRequested.connect(self.deletePageRequested)
        self._thumb_strip.pagesReordered.connect(self.pagesReordered)

    def _request_rotate(self, degrees: int) -> None:
        if self._selected_page_id:
            self.rotateRequested.emit(self._selected_page_id, degrees % 360)

    def _on_page_selected(self, page_id: str) -> None:
        self._selected_page_id = page_id
        self.pageSelected.emit(page_id)

    def set_document(self, document: Document) -> None:
        self._thumb_strip.set_pages(document.pages)
        has_pages = not document.is_empty
        self._rotate_left_btn.setEnabled(has_pages)
        self._rotate_right_btn.setEnabled(has_pages)

        if not has_pages:
            self._selected_page_id = None
            self._current_pixmap = None
            self._preview_label.setPixmap(QPixmap())
            self._preview_label.setText(_EMPTY_TEXT)
            return

        selected_id = self._selected_page_id
        if not selected_id or not any(p.id == selected_id for p in document.pages):
            selected_id = document.pages[-1].id
            self._selected_page_id = selected_id
        self._show_page(document.get_page(selected_id))

    def _show_page(self, page) -> None:
        pixmap = QPixmap(str(page.image_path))
        if not pixmap.isNull() and page.rotation:
            pixmap = pixmap.transformed(
                QTransform().rotate(page.rotation), Qt.TransformationMode.SmoothTransformation
            )
        self._current_pixmap = pixmap
        self._render_scaled_preview()

    def _render_scaled_preview(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        scaled = self._current_pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_scaled_preview()
