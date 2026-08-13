from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    """Schwebende Kurzmeldung oben mittig über dem Fensterinhalt (`toastStyle` im Mockup) —
    z.B. Bestätigung nach 'Speicherort öffnen' oder nach dem Speichern eines Scans.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setContentsMargins(18, 10, 18, 10)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration_ms: int = 2400) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            x = (parent.width() - self.width()) // 2
            self.move(x, 52)
        self.raise_()
        self.show()
        self._timer.start(duration_ms)
