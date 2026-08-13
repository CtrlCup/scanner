import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from scanner_app.resources import resource_path
from scanner_app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    # Erzwingt den plattformunabhängigen "Fusion"-Stil statt des nativen OS-Stils
    # (z.B. "windowsvista" unter Windows) — native Stile zeichnen für Buttons, Slider &
    # Co. eigene Chrome-Elemente, die unser QSS (abgerundete Ecken, eigene Slider-Handles
    # etc.) nur teilweise überschreiben kann. Fusion respektiert Stylesheets vollständig
    # und ist damit Voraussetzung für das erklärte Ziel "sieht auf allen Plattformen
    # exakt gleich aus" (siehe CLAUDE.md).
    app.setStyle("Fusion")
    app.setApplicationName("Scanner")
    app.setWindowIcon(QIcon(str(resource_path("icon.png"))))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
