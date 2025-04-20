from PySide6.QtWidgets import QLabel

class AspectRatioLabel(QLabel):
    """
    QLabel that maintains a fixed aspect ratio based on its width.
    """
    def __init__(self, aspect_w=16, aspect_h=9, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aspect_w = aspect_w
        self.aspect_h = aspect_h

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(width * self.aspect_h / self.aspect_w)
