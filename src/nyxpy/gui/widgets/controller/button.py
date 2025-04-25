from PySide6.QtWidgets import QPushButton
from nyxpy.framework.core.constants import Button
from typing import Optional, Tuple


class ControllerButton(QPushButton):
    """カスタムスタイルのコントローラーボタン"""

    def __init__(
        self,
        text: str = "",
        parent: Optional[QPushButton] = None,
        button_type: Optional[Button] = None,
        size: Tuple[int, int] = (30, 30),
        radius: int = 15,
        is_rectangular: bool = False,
    ) -> None:
        super().__init__(text, parent)
        self.button_type = button_type
        self.setFixedSize(size[0], size[1])

        # 四角形か円形かによってスタイルを変更
        if is_rectangular:
            self.setStyleSheet("""        
                QPushButton {{
                    background-color: #444;
                    color: white;
                    border-radius: 5px;
                    border: 2px solid #555;
                    font-size: 9px;
                    font-weight: bold;
                }}
                QPushButton:pressed {{
                    background-color: #666;
                    border: 2px solid #888;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #444;
                    color: white;
                    border-radius: {radius}px;
                    border: 2px solid #555;
                    font-size: 9px;
                    font-weight: bold;
                }}
                QPushButton:pressed {{
                    background-color: #666;
                    border: 2px solid #888;
                }}
            """)
