import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app import __version__, theme
from app.gui.main_window import MainWindow
from app.settings import Settings


def main():
    QCoreApplication.setOrganizationName("VeyloraLabs")
    QCoreApplication.setApplicationName("VeyloraNotes")
    QCoreApplication.setApplicationVersion(__version__)
    app = QApplication(sys.argv)
    app.setDesktopFileName("veyloranotes")
    theme.apply(app)
    paths = [argument for argument in sys.argv[1:] if not argument.startswith("-")]
    window = MainWindow(Settings(), paths)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
