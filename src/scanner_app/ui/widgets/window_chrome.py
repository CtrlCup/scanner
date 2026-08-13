from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scanner_app.ui import icons


class _WinButton(QPushButton):
    def __init__(self, icon_spec: tuple[str, str], tooltip: str, *, close: bool = False) -> None:
        super().__init__()
        self.setObjectName("winButton")
        self.setProperty("close", "true" if close else "false")
        self.setFixedSize(46, 40)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_spec = icon_spec
        self.set_color("#1b1b1b")

    def set_color(self, color: str) -> None:
        self.setIcon(icons.svg_icon(self._icon_spec, color, size=10))
        self.setIconSize(QSize(10, 10))


class TitleBar(QWidget):
    """Selbstgezeichnete Titelleiste (kein natives Fensterdekor) — sieht dadurch auf
    Windows und Linux exakt gleich aus, wie im Design-Mockup vorgegeben. Ziehen bewegt
    das Fenster über QWindow.startSystemMove(), Doppelklick maximiert/stellt wieder her.
    """

    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(16, 16)
        layout.addWidget(self._icon_label)

        self._title_label = QLabel("Scanner")
        self._title_label.setObjectName("titleLabel")
        layout.addWidget(self._title_label)
        layout.addStretch()

        self._minimize_btn = _WinButton(icons.WIN_MINIMIZE, "Minimieren")
        self._maximize_btn = _WinButton(icons.WIN_MAXIMIZE, "Maximieren")
        self._close_btn = _WinButton(icons.WIN_CLOSE, "Schließen", close=True)
        self._minimize_btn.clicked.connect(self.minimizeRequested)
        self._maximize_btn.clicked.connect(self.maximizeRequested)
        self._close_btn.clicked.connect(self.closeRequested)
        for button in (self._minimize_btn, self._maximize_btn, self._close_btn):
            layout.addWidget(button)

        self._drag_start: QPoint | None = None

    def apply_colors(self, accent: str, title_color: str, button_color: str) -> None:
        self._icon_label.setPixmap(icons.svg_icon(icons.SCANNER, accent, size=16).pixmap(16, 16))
        for button in (self._minimize_btn, self._maximize_btn, self._close_btn):
            button.set_color(button_color)

    def set_maximized(self, maximized: bool) -> None:
        self._maximize_btn._icon_spec = icons.WIN_RESTORE if maximized else icons.WIN_MAXIMIZE
        self._maximize_btn.setToolTip("Wiederherstellen" if maximized else "Maximieren")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximizeRequested.emit()
            return
        super().mouseDoubleClickEvent(event)


class PathPopover(QWidget):
    """Schwebender Hinweis, der beim Hover über das Ordner-Icon den aktuellen
    Speicherpfad zeigt — entspricht `pathPopoverStyle` im Design-Mockup.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # `parent` übergeben (statt None): das Popup bleibt trotz eigener Fenster-Flags ein
        # Qt-Kind von IconRail und wird beim Zerstören des Elternfensters automatisch mit
        # entsorgt — ohne Parent kollidiert die manuelle hide()-Anweisung in
        # IconRail.hideEvent() sonst mit der Zerstörungsreihenfolge beim Interpreter-Shutdown.
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("pathPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        self._title = QLabel("Speicherpfad öffnen")
        self._title.setObjectName("pathPopoverLabel")
        self._value = QLabel()
        self._value.setObjectName("pathPopoverValue")
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def show_at(self, anchor: QWidget, path: str) -> None:
        self._value.setText(path)
        self.adjustSize()
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + anchor.width() + 8
        y = top_left.y() + anchor.height() // 2 - self.height() // 2
        self.move(x, y)
        self.show()


class IconRail(QWidget):
    """Schmale Icon-Leiste ganz links: großer Scan-Button oben, Ordner (Speicherort
    öffnen) + Zahnrad (Einstellungen) unten — entspricht `railStyle` im Mockup.
    """

    scanRequested = Signal()
    openFolderRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("iconRail")
        self.setFixedWidth(56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(10)

        self._scan_btn = QPushButton()
        self._scan_btn.setObjectName("railScanButton")
        self._scan_btn.setFixedSize(38, 38)
        self._scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_btn.setToolTip("Neue Seite scannen")
        self._scan_btn.clicked.connect(self.scanRequested)
        layout.addWidget(self._scan_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        self._folder_btn = QPushButton()
        self._folder_btn.setObjectName("railIconButton")
        self._folder_btn.setFixedSize(38, 38)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.clicked.connect(self.openFolderRequested)
        self._folder_btn.installEventFilter(self)
        layout.addWidget(self._folder_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._settings_btn = QPushButton()
        self._settings_btn.setObjectName("railIconButton")
        self._settings_btn.setProperty("active", "true")
        self._settings_btn.setFixedSize(38, 38)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setToolTip("Einstellungen")
        self._settings_btn.clicked.connect(self.settingsRequested)
        layout.addWidget(self._settings_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._popover = PathPopover(self)
        self._save_path = ""
        self._folder_btn.setToolTip("Speicherort öffnen")

    def set_save_path(self, path: str) -> None:
        self._save_path = path

    def apply_colors(self, accent: str, rail_icon_color: str) -> None:
        self._scan_btn.setIcon(icons.svg_icon(icons.SCANNER, "#ffffff", size=18))
        self._scan_btn.setIconSize(QSize(18, 18))
        self._folder_btn.setIcon(icons.svg_icon(icons.FOLDER, rail_icon_color, size=18))
        self._folder_btn.setIconSize(QSize(18, 18))
        self._settings_btn.setIcon(icons.svg_icon(icons.GEAR, accent, size=18))
        self._settings_btn.setIconSize(QSize(18, 18))

    def eventFilter(self, watched, event) -> bool:
        if watched is self._folder_btn:
            if event.type() == event.Type.Enter:
                self._popover.show_at(self._folder_btn, self._save_path)
            elif event.type() == event.Type.Leave:
                self._popover.hide()
        return super().eventFilter(watched, event)

    def hideEvent(self, event) -> None:
        try:
            self._popover.hide()
        except RuntimeError:
            pass  # C++-Objekt beim Interpreter-Shutdown ggf. bereits zerstört
        super().hideEvent(event)
