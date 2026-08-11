from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget


class ToggleSwitch(QAbstractButton):
    """Selbstgezeichneter An/Aus-Schalter mit animiertem Handle (kein natives QCheckBox-Icon,
    das würde nicht zum restlichen, kartenbasierten Design passen).
    """

    def __init__(self, parent: QWidget | None = None, accent: str = "#0067C0") -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)
        self._accent = QColor(accent)
        self._track_off = QColor("#3a3b40")
        self._handle_pos = 3.0
        self._anim = QPropertyAnimation(self, b"handlePos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate_to_state)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._handle_pos)
        self._anim.setEndValue(21.0 if checked else 3.0)
        self._anim.start()

    def _get_handle_pos(self) -> float:
        return self._handle_pos

    def _set_handle_pos(self, value: float) -> None:
        self._handle_pos = value
        self.update()

    handlePos = Property(float, _get_handle_pos, _set_handle_pos)

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self.update()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._handle_pos = 21.0 if checked else 3.0

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        track_color = self._accent if self.isChecked() else self._track_off
        if not self.isEnabled():
            track_color = QColor(self._track_off).darker(120)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(self._handle_pos, 3, 18, 18))
