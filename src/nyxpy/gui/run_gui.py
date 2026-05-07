import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from nyxpy.gui.main_window import MainWindow


def main():
    # Initialize required directories
    for d in ("macros", "snapshots", "resources", "runs"):
        Path(d).mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
