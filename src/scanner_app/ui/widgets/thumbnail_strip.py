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

_TILE_SIZE = 90


class ThumbnailTile(QWidget):
    deleteClicked = Signal()

    def __init__(self, page: Page, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thumbnailTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._image_label = QLabel(self)
        self._image_label.setFixedSize(_TILE_SIZE, _TILE_SIZE)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_label)
        self.set_page(page)

        delete_button = QPushButton("×", self._image_label)
        delete_button.setObjectName("deleteChip")
        delete_button.setFixedSize(20, 20)
        delete_button.move(_TILE_SIZE - 22, 2)
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.clicked.connect(self.deleteClicked.emit)

    def set_page(self, page: Page) -> None:
        pixmap = QPixmap(str(page.image_path))
        if not pixmap.isNull():
            if page.rotation:
                pixmap = pixmap.transformed(
                    QTransform().rotate(page.rotation), Qt.TransformationMode.SmoothTransformation
                )
            pixmap = pixmap.scaled(
                _TILE_SIZE - 8,
                _TILE_SIZE - 8,
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
        self.setObjectName("thumbnailStrip")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Snap)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(8)
        self.setFixedHeight(120)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.model().rowsMoved.connect(self._emit_reordered)
        self.itemSelectionChanged.connect(self._emit_selected)

    def set_pages(self, pages: list[Page]) -> None:
        previously_selected = self._selected_page_id()
        self.blockSignals(True)
        self.clear()
        for page in pages:
            self._add_item(page)
        self.blockSignals(False)

        if previously_selected and any(p.id == previously_selected for p in pages):
            self.select_page(previously_selected)
        elif pages:
            self.select_page(pages[-1].id)

    def select_page(self, page_id: str) -> None:
        for index in range(self.count()):
            item = self.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == page_id:
                self.setCurrentItem(item)
                return

    def _add_item(self, page: Page) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, page.id)
        item.setSizeHint(QSize(_TILE_SIZE + 8, _TILE_SIZE + 8))
        self.addItem(item)
        tile = ThumbnailTile(page)
        tile.deleteClicked.connect(lambda page_id=page.id: self.pageDeleteRequested.emit(page_id))
        self.setItemWidget(item, tile)

    def _selected_page_id(self) -> str | None:
        items = self.selectedItems()
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def _emit_selected(self) -> None:
        page_id = self._selected_page_id()
        if page_id:
            self.pageSelected.emit(page_id)

    def _emit_reordered(self, *_args) -> None:
        ids = [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        self.pagesReordered.emit(ids)
