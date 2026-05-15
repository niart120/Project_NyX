from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLabel


def apply_pane_title_font(label: QLabel) -> None:
    font = label.font()
    font.setBold(True)
    label.setFont(font)


def log_view_font() -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font
