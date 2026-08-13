from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from scanner_app.models.document import Document
from scanner_app.ui import icons
from scanner_app.ui.widgets.thumbnail_strip import ThumbnailStrip

_EMPTY_TEXT = "Noch keine Seite gescannt"
_PAGE_ASPECT = 380 / 536  # Breite/Höhe der Papier-Karte im Design-Mockup


class PreviewPanel(QWidget):
    """Rechte Seite: große Vorschau der fokussierten Seite als weiße 'Papier-Karte' mit
    Schatten (wie im Design-Mockup), Rotieren-Buttons in der Kopfzeile, Thumbnail-Leiste
    aller Seiten darunter (Löschen per ×, Neuordnen per Drag&Drop).
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
        self._has_pages = False
        self._thumbnails_enabled = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName("previewTopBar")
        top_bar.setFixedHeight(44)
        top_row = QHBoxLayout(top_bar)
        top_row.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Vorschau")
        title.setObjectName("previewTitle")
        top_row.addWidget(title)
        top_row.addStretch()

        self._rotate_left_btn = QPushButton()
        self._rotate_right_btn = QPushButton()
        for button, icon_spec, tooltip in (
            (self._rotate_left_btn, icons.ROTATE_LEFT, "Seite nach links drehen"),
            (self._rotate_right_btn, icons.ROTATE_RIGHT, "Seite nach rechts drehen"),
        ):
            button.setObjectName("railIconButton")
            button.setFixedSize(30, 30)
            button.setIcon(icons.svg_icon(icon_spec, "#8a8a8a", size=16))
            button.setToolTip(tooltip)
            button.setEnabled(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            top_row.addWidget(button)
        self._counter_label = QLabel()
        self._counter_label.setObjectName("previewCounter")
        top_row.addSpacing(12)
        top_row.addWidget(self._counter_label)
        layout.addWidget(top_bar)

        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(24, 24, 24, 24)

        self._center_stack = QStackedWidget()
        center_layout.addWidget(self._center_stack)
        layout.addWidget(center, stretch=1)

        self._paper_card = QLabel()
        self._paper_card.setObjectName("paperCard")
        self._paper_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shadow = QGraphicsDropShadowEffect(self._paper_card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        self._paper_card.setGraphicsEffect(shadow)
        self._center_stack.addWidget(self._paper_card)

        empty_state = QWidget()
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel()
        empty_icon.setPixmap(icons.svg_icon(icons.DOCUMENT_OUTLINE, "#9a9a9a", size=36).pixmap(36, 36))
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_text = QLabel(_EMPTY_TEXT)
        empty_text.setObjectName("emptyStateLabel")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)
        self._center_stack.addWidget(empty_state)

        self._thumb_strip = ThumbnailStrip()
        layout.addWidget(self._thumb_strip)

        self._rotate_left_btn.clicked.connect(lambda: self._request_rotate(-90))
        self._rotate_right_btn.clicked.connect(lambda: self._request_rotate(90))
        self._thumb_strip.pageSelected.connect(self._on_page_selected)
        self._thumb_strip.pageDeleteRequested.connect(self.deletePageRequested)
        self._thumb_strip.pagesReordered.connect(self.pagesReordered)

    def set_thumbnails_visible(self, visible: bool) -> None:
        self._thumbnails_enabled = visible
        self._thumb_strip.setVisible(visible and self._has_pages)

    def _request_rotate(self, degrees: int) -> None:
        if self._selected_page_id:
            self.rotateRequested.emit(self._selected_page_id, degrees % 360)

    def _on_page_selected(self, page_id: str) -> None:
        self._selected_page_id = page_id
        self.pageSelected.emit(page_id)

    def set_document(self, document: Document) -> None:
        self._thumb_strip.set_pages(document.pages)
        has_pages = not document.is_empty
        self._has_pages = has_pages
        self._thumb_strip.setVisible(self._thumbnails_enabled and has_pages)
        self._rotate_left_btn.setEnabled(has_pages)
        self._rotate_right_btn.setEnabled(has_pages)

        if not has_pages:
            self._selected_page_id = None
            self._current_pixmap = None
            self._paper_card.setPixmap(QPixmap())
            self._center_stack.setCurrentIndex(1)
            self._counter_label.setText("Keine Seite gescannt")
            return

        self._center_stack.setCurrentIndex(0)
        selected_id = self._selected_page_id
        if not selected_id or not any(p.id == selected_id for p in document.pages):
            selected_id = document.pages[-1].id
            self._selected_page_id = selected_id
        index = next(i for i, p in enumerate(document.pages) if p.id == selected_id)
        self._counter_label.setText(f"Seite {index + 1} von {len(document.pages)}")
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
        available = self._center_stack.size()
        max_height = available.height()
        max_width = min(available.width(), int(max_height * _PAGE_ASPECT))
        if max_height <= 0 or max_width <= 0:
            return
        card_size = self._current_pixmap.size().scaled(
            max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio
        )
        self._paper_card.setFixedSize(card_size)
        scaled = self._current_pixmap.scaled(
            card_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._paper_card.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_scaled_preview()
