import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from scanner_app.resources import resource_path
from scanner_app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Scanner")
    app.setWindowIcon(QIcon(str(resource_path("icon.png"))))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
