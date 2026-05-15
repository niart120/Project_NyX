from PySide6.QtWidgets import QPushButton

from nyxpy.framework.core.constants import Button


class ControllerButton(QPushButton):
    """カスタムスタイルのコントローラーボタン"""

    def __init__(
        self,
        text: str = "",
        parent: QPushButton | None = None,
        button_type: Button | None = None,
        size: tuple[int, int] = (30, 30),
        radius: int = 15,
        is_rectangular: bool = False,
    ) -> None:
        super().__init__(text, parent)
        self.button_type = button_type
        self.is_rectangular = is_rectangular
        self.configure_size(size, radius=radius, font_size=9)

    def configure_size(
        self,
        size: tuple[int, int],
        *,
        radius: int,
        font_size: int,
    ) -> None:
        self.setFixedSize(size[0], size[1])
        radius_px = min(radius, max(1, min(size) // 2))
        border_radius = min(5, radius_px) if self.is_rectangular else radius_px
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #444;
                color: white;
                border-radius: {border_radius}px;
                border: 2px solid #555;
                font-size: {font_size}px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: #666;
                border: 2px solid #888;
            }}
        """)
