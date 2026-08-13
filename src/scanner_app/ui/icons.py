"""SVG-Icons, 1:1 aus dem vorgegebenen Design-Mockup (Dokumentenscanner-UI.html) übernommen.

Jedes Icon ist ein reines Pfad-Fragment (kein <svg>-Wrapper) mit `viewBox`, das per
:func:`svg_icon` mit einer Laufzeitfarbe gerendert wird — Icons passen sich so ohne
mehrere Bild-Assets an Akzentfarbe/Hell-Dunkel-Modus an, genau wie im Mockup
(`stroke="currentColor"` bzw. `stroke="{{ accent }}"`).
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# (viewBox, inner_svg_markup) — "currentColor" wird beim Rendern durch die gewünschte Farbe ersetzt.
SCANNER = (
    "0 0 24 24",
    '<rect x="4" y="3" width="16" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/>'
    + '<path d="M2 17h20l-2 4H4l-2-4z" fill="currentColor" stroke="none"/>',
)
DOCUMENT_OUTLINE = (
    "0 0 24 24",
    '<rect x="4" y="3" width="16" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/>'
    + '<path d="M2 17h20l-2 4H4l-2-4z" fill="none" stroke="currentColor" stroke-width="1.5"/>',
)
FOLDER = (
    "0 0 24 24",
    '<path fill="none" stroke="currentColor" stroke-width="1.7" '
    + 'd="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
)
_GEAR_PATH = (
    "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 "
    "1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 "
    "0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 "
    "0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 "
    "1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 "
    "2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 "
    "0-1.51 1z"
)
GEAR = (
    "0 0 24 24",
    '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/>'
    + f'<path fill="none" stroke="currentColor" stroke-width="1.7" d="{_GEAR_PATH}"/>',
)
CHEVRON_DOWN = ("0 0 24 24", '<path fill="none" stroke="currentColor" stroke-width="2" d="M6 9l6 6 6-6"/>')
CHECK = ("0 0 24 24", '<path fill="none" stroke="currentColor" stroke-width="2.5" d="M5 13l4 4L19 7"/>')
PLUS = (
    "0 0 24 24",
    '<line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" stroke-width="2"/>'
    + '<line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" stroke-width="2"/>',
)
BACK_ARROW = ("0 0 24 24", '<path fill="none" stroke="currentColor" stroke-width="2" d="M15 18l-6-6 6-6"/>')
WIN_MINIMIZE = ("0 0 10 10", '<line x1="0" y1="5" x2="10" y2="5" stroke="currentColor" stroke-width="1"/>')
WIN_MAXIMIZE = (
    "0 0 10 10",
    '<rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1"/>',
)
WIN_RESTORE = (
    "0 0 10 10",
    '<rect x="0.5" y="1.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1"/>'
    + '<path fill="none" stroke="currentColor" stroke-width="1" d="M2.5 1.5v-1h7v7h-1"/>',
)
WIN_CLOSE = (
    "0 0 10 10",
    '<line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" stroke-width="1"/>'
    + '<line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" stroke-width="1"/>',
)
ROTATE_LEFT = (
    "0 0 24 24",
    '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M4 12a8 8 0 1 1 2.5 5.8"/>'
    + '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M4 8v4.5H8.5"/>',
)
ROTATE_RIGHT = (
    "0 0 24 24",
    '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M20 12a8 8 0 1 0-2.5 5.8"/>'
    + '<path fill="none" stroke="currentColor" stroke-width="1.8" d="M20 8v4.5h-4.5"/>',
)


def svg_icon(spec: tuple[str, str], color: str, size: int = 18) -> QIcon:
    view_box, inner = spec
    markup = inner.replace("currentColor", color)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">{markup}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    dpr = 2.0
    pixmap = QPixmap(QSize(int(size * dpr), int(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    # Ziel-Rechteck ist Pflicht: ohne es zeichnet render() das SVG in seiner nativen
    # viewBox-Größe (hier 24x24 bzw. 10x10 SVG-Einheiten) oben links in die Pixmap statt
    # auf deren volle Größe skaliert — sichtbar als abgeschnittenes Mini-Icon in der Ecke.
    # Logische (nicht physische) Größe: QPainter rechnet auf einer Pixmap mit gesetztem
    # devicePixelRatio bereits in skalierten Koordinaten — size*dpr würde hier doppelt
    # skalieren und nur noch das obere linke Viertel des Icons sichtbar lassen.
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


_ICON_CACHE_DIR = Path(tempfile.gettempdir()) / "scanner-app-icons"


def icon_file_path(spec: tuple[str, str], color: str, size: int = 12) -> str:
    """Rendert ein Icon als PNG-Datei und gibt dessen Pfad zurück — für die seltenen Stellen,
    an denen Qt-Stylesheets ein `image: url(...)` brauchen (z.B. QComboBox::down-arrow), das
    anders als `QPushButton.setIcon()` keine in-memory QIcon/QPixmap akzeptiert.
    """
    _ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{spec}{color}{size}".encode()).hexdigest()[:16]
    path = _ICON_CACHE_DIR / f"{key}.png"
    if not path.exists():
        svg_icon(spec, color, size=size).pixmap(size, size).save(str(path))
    return path.as_posix()
