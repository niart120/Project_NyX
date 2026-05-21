"""GUI 共通 typography helper。"""

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLabel

PANE_TITLE_HEIGHT = 24


def apply_pane_title_font(label: QLabel) -> None:
    """Pane title 用の太字 font と高さを label に適用します。"""
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setFixedHeight(PANE_TITLE_HEIGHT)


def log_view_font() -> QFont:
    """ログ表示向けの等幅 font を返します。"""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font
