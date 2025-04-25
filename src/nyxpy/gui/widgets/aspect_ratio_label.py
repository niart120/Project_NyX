from PySide6.QtWidgets import QLabel
from typing import Any

class AspectRatioLabel(QLabel):
    """
    QLabel that maintains a fixed aspect ratio based on its width.
    """
    def __init__(self, aspect_w: int = 16, aspect_h: int = 9, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.aspect_w = aspect_w
        self.aspect_h = aspect_h

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return int(width * self.aspect_h / self.aspect_w)