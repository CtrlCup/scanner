from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

_TICK_MS = 40
_STEP_DEGREES = 30
_ARC_SPAN_DEGREES = 270


class Spinner(QWidget):
    """Selbstgezeichneter rotierender Lade-Indikator (kein QMovie/GIF-Asset nötig) —
    entspricht `spinnerStyle` im Design-Mockup, dessen CSS-Keyframe-Animation Qt-Stylesheets
    nicht unterstützen.
    """

    def __init__(self, parent: QWidget | None = None, size: int = 14, color: str = "#ffffff") -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start(_TICK_MS)
        self.show()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + _STEP_DEGREES) % 360
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawArc(rect, self._angle * 16, _ARC_SPAN_DEGREES * 16)
