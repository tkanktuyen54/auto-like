"""Run with python -m autoclap."""

import logging
import os
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from .storage import data_directory
from .ui import MainWindow, STYLE, app_icon


def main() -> int:
    if os.name != "nt":
        os.umask(0o077)
    # Do not let third-party logs print account/session details to the console.
    logging.getLogger("telethon").addHandler(logging.NullHandler())
    logging.getLogger("telethon").propagate = False
    app = QApplication(sys.argv)
    app.setApplicationName("AutoClap")
    app.setOrganizationName("AutoClap")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI" if os.name == "nt" else "Helvetica Neue", 10))
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    directory = data_directory()
    lock = QLockFile(str(directory / "app.lock"))
    if not lock.tryLock(0):
        QMessageBox.information(None, "AutoClap", "AutoClap đã mở. Hãy dùng cửa sổ đang chạy.")
        return 0
    window = MainWindow(directory)
    window.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
