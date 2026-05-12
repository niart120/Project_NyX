import sys

from PySide6.QtWidgets import QApplication

from nyxpy.framework.core.settings.workspace import ensure_workspace, resolve_project_root
from nyxpy.gui.main_window import MainWindow


def main():
    project_root = resolve_project_root(allow_current_as_new=True)
    paths = ensure_workspace(project_root)
    app = QApplication(sys.argv)
    window = MainWindow(project_root=paths.project_root)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
