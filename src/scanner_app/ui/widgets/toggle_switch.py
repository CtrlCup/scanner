from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget


class ToggleSwitch(QAbstractButton):
    """Selbstgezeichneter An/Aus-Schalter mit animiertem Handle (kein natives QCheckBox-Icon,
    das würde nicht zum restlichen, kartenbasierten Design passen).
    """

    def __init__(
        self, parent: QWidget | None = None, accent: str = "#0067C0", track_off: str = "#33000000"
    ) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(38, 22)
        self._accent = QColor(accent)
        self._track_off = QColor(track_off)
        self._handle_pos = 2.0
        self._anim = QPropertyAnimation(self, b"handlePos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate_to_state)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._handle_pos)
        self._anim.setEndValue(18.0 if checked else 2.0)
        self._anim.start()

    def set_track_off_color(self, color: str) -> None:
        self._track_off = QColor(color)
        self.update()

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
        # _handle_pos MUSS vor super().setChecked() gesetzt werden: das löst synchron das
        # toggled-Signal aus, das _animate_to_state per aktuellem _handle_pos als Startwert
        # anstößt. Falsche Reihenfolge lässt die Animation kurz zur alten Position zurück-
        # springen, bevor sie zur neuen zurückanimiert — sichtbar als falsch positionierter
        # Handle direkt nach dem (nicht-interaktiven) Setzen des Anfangszustands.
        self._handle_pos = 18.0 if checked else 2.0
        super().setChecked(checked)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        track_color = self._accent if self.isChecked() else self._track_off
        if not self.isEnabled():
            track_color = QColor(self._track_off).darker(120)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 11, 11)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(self._handle_pos, 2, 18, 18))
