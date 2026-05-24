"""Virtual controller の button widget。"""

from PySide6.QtWidgets import QPushButton, QWidget

from nyxpy.framework.core.constants import Button


class ControllerButton(QPushButton):
    """カスタムスタイルのコントローラーボタン"""

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        button_type: Button | None = None,
        size: tuple[int, int] = (30, 30),
        radius: int = 15,
        is_rectangular: bool = False,
    ) -> None:
        """Button 種別と表示寸法を設定します。"""
        if button_type is None:
            raise ValueError("button_type is required")
        super().__init__(text, parent)
        self.button_type = button_type
        self.is_rectangular = is_rectangular
        self.configure_size(size, radius=radius, font_point_size=9)

    def configure_size(
        self,
        size: tuple[int, int],
        *,
        radius: int,
        font_point_size: int,
    ) -> None:
        self.setFixedSize(size[0], size[1])
        font = self.font()
        font.setBold(True)
        font.setPointSize(font_point_size)
        self.setFont(font)
        radius_px = min(radius, max(1, min(size) // 2))
        border_radius = min(5, radius_px) if self.is_rectangular else radius_px
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #444;
                color: white;
                border-radius: {border_radius}px;
                border: 2px solid #555;
            }}
            QPushButton:pressed {{
                background-color: #666;
                border: 2px solid #888;
            }}
        """)
