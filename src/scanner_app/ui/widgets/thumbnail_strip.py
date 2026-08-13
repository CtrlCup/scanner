from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scanner_app.models.document import Page

_TILE_WIDTH = 64
_TILE_HEIGHT = 84


class ThumbnailTile(QWidget):
    """Seiten-Kachel — entspricht der Thumbnail-Kachel im Design-Mockup: weiße Karte,
    Löschen-Kreuz oben rechts, Seitenzahl unten rechts, Akzent-Rahmen wenn ausgewählt.
    """

    deleteClicked = Signal()

    def __init__(self, page: Page, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thumbnailTile")
        self.setFixedSize(_TILE_WIDTH, _TILE_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_label)
        self.set_page(page)

        self._badge = QLabel(str(index), self)
        self._badge.setObjectName("thumbPageBadge")
        self._badge.adjustSize()
        self._badge.move(_TILE_WIDTH - self._badge.width() - 6, _TILE_HEIGHT - self._badge.height() - 4)

        delete_button = QPushButton("×", self)
        delete_button.setObjectName("deleteChip")
        delete_button.setFixedSize(18, 18)
        delete_button.move(_TILE_WIDTH - 15, -3)
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.clicked.connect(self.deleteClicked.emit)
        delete_button.raise_()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_page(self, page: Page) -> None:
        pixmap = QPixmap(str(page.image_path))
        if not pixmap.isNull():
            if page.rotation:
                pixmap = pixmap.transformed(
                    QTransform().rotate(page.rotation), Qt.TransformationMode.SmoothTransformation
                )
            pixmap = pixmap.scaled(
                _TILE_WIDTH - 12,
                _TILE_HEIGHT - 12,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._image_label.setPixmap(pixmap)


class ThumbnailStrip(QListWidget):
    """Horizontale Seitenleiste mit Drag&Drop-Neuanordnung (native Qt-InternalMove) sowie
    Lösch-Button pro Kachel. Auswahl einer Kachel bestimmt, welche Seite oben rotiert wird.
    """

    pageSelected = Signal(str)
    pageDeleteRequested = Signal(str)
    pagesReordered = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thumbStrip")
        self.setFrameShape(QListWidget.Shape.NoFrame)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Snap)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(6)
        self.setFixedHeight(108)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.model().rowsMoved.connect(self._emit_reordered)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_pages(self, pages: list[Page]) -> None:
        previously_selected = self._selected_page_id()
        self.blockSignals(True)
        self.clear()
        for index, page in enumerate(pages, start=1):
            self._add_item(page, index)
        self.blockSignals(False)

        if previously_selected and any(p.id == previously_selected for p in pages):
            self.select_page(previously_selected)
        elif pages:
            self.select_page(pages[-1].id)
        else:
            self._on_selection_changed()

    def select_page(self, page_id: str) -> None:
        for index in range(self.count()):
            item = self.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == page_id:
                self.setCurrentItem(item)
                return

    def _add_item(self, page: Page, index: int) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, page.id)
        item.setSizeHint(QSize(_TILE_WIDTH + 6, _TILE_HEIGHT + 6))
        self.addItem(item)
        tile = ThumbnailTile(page, index)
        tile.deleteClicked.connect(lambda page_id=page.id: self.pageDeleteRequested.emit(page_id))
        self.setItemWidget(item, tile)

    def _selected_page_id(self) -> str | None:
        items = self.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _on_selection_changed(self) -> None:
        selected_id = self._selected_page_id()
        for index in range(self.count()):
            item = self.item(index)
            tile = self.itemWidget(item)
            if isinstance(tile, ThumbnailTile):
                tile.set_selected(item.data(Qt.ItemDataRole.UserRole) == selected_id)
        if selected_id:
            self.pageSelected.emit(selected_id)

    def _emit_reordered(self, *_args) -> None:
        ids = [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        self.pagesReordered.emit(ids)
