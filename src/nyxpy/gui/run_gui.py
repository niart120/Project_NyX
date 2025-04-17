import sys
import os
from PySide6.QtWidgets import QApplication
from nyxpy.gui.main_window import MainWindow

def main():
    # Initialize required directories
    for d in ("macros", "snapshots", "static"): 
        os.makedirs(d, exist_ok=True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
