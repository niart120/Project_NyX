"""縦横比を維持して pixmap を表示する label。"""

from typing import Any

from PySide6.QtWidgets import QLabel


class AspectRatioLabel(QLabel):
    """QLabel that maintains a fixed aspect ratio based on its width."""

    def __init__(self, aspect_w: int = 16, aspect_h: int = 9, *args: Any, **kwargs: Any) -> None:
        """基準 aspect ratio と QLabel 初期化引数を保持します。"""
        super().__init__(*args, **kwargs)
        self.aspect_w = aspect_w
        self.aspect_h = aspect_h

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return int(width * self.aspect_h / self.aspect_w)
