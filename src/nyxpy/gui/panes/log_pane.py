from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit

class LogPane(QWidget):
    """
    Pane for displaying real-time logs in a read-only text view.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

    def append(self, message: str):
        """Append a new log message to the view."""
        self.view.appendPlainText(message)
