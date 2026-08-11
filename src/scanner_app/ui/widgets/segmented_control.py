from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    """Gruppe exklusiv wählbarer Buttons in einer Pille (z.B. Quelle: Automatisch/Flachbett/Einzug)."""

    currentChanged = Signal(str)

    def __init__(self, options: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for option in options:
            button = QPushButton(option)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button)
            layout.addWidget(button, stretch=1)
            self._buttons[option] = button
            button.clicked.connect(lambda _checked, o=option: self.currentChanged.emit(o))

        if options:
            self._buttons[options[0]].setChecked(True)

    def current(self) -> str:
        for name, button in self._buttons.items():
            if button.isChecked():
                return name
        return ""

    def set_current(self, option: str) -> None:
        button = self._buttons.get(option)
        if button is not None:
            button.setChecked(True)
