from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QWidget

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.logger import LoggerPort
from nyxpy.gui.models.virtual_controller_model import VirtualControllerModel
from nyxpy.gui.widgets.controller.analog_stick import AnalogStick
from nyxpy.gui.widgets.controller.button import ControllerButton
from nyxpy.gui.widgets.controller.dpad import DPad


@dataclass(frozen=True)
class _WidgetRect:
    x: int
    y: int
    width: int
    height: int


_BASE_WIDTH = 280
_BASE_HEIGHT = 240

_BASE_RECTS: dict[str, _WidgetRect] = {
    "btn_zl": _WidgetRect(16, 4, 34, 22),
    "btn_l": _WidgetRect(76, 4, 34, 22),
    "btn_r": _WidgetRect(168, 4, 34, 22),
    "btn_zr": _WidgetRect(228, 4, 34, 22),
    "btn_minus": _WidgetRect(56, 38, 30, 24),
    "btn_capture": _WidgetRect(92, 38, 30, 24),
    "btn_home": _WidgetRect(158, 38, 30, 24),
    "btn_plus": _WidgetRect(194, 38, 30, 24),
    "left_stick": _WidgetRect(20, 74, 64, 64),
    "btn_ls": _WidgetRect(37, 138, 30, 20),
    "btn_x": _WidgetRect(204, 64, 28, 28),
    "btn_y": _WidgetRect(174, 94, 28, 28),
    "btn_a": _WidgetRect(234, 94, 28, 28),
    "btn_b": _WidgetRect(204, 124, 28, 28),
    "dpad": _WidgetRect(38, 158, 72, 72),
    "right_stick": _WidgetRect(194, 160, 64, 64),
    "btn_rs": _WidgetRect(211, 224, 30, 16),
}


class VirtualControllerPane(QWidget):
    """仮想コントローラーのメインペイン"""

    def __init__(self, logger: LoggerPort, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = VirtualControllerModel(logger=logger)
        self._layout_size = QSize(280, 280)
        self._create_widgets()
        self._connect_buttons()
        self.apply_layout_size(self._layout_size.width(), self._layout_size.height())

    def _create_widgets(self) -> None:
        self.btn_zl = ControllerButton("ZL", self, Button.ZL, is_rectangular=True)
        self.btn_l = ControllerButton("L", self, Button.L, is_rectangular=True)
        self.btn_minus = ControllerButton("-", self, Button.MINUS)
        self.btn_capture = ControllerButton("📷", self, Button.CAP)
        self.left_stick = AnalogStick(self, is_left=True)
        self.btn_ls = ControllerButton("LS", self, Button.LS, is_rectangular=True)
        self.dpad = DPad(self)

        self.btn_r = ControllerButton("R", self, Button.R, is_rectangular=True)
        self.btn_zr = ControllerButton("ZR", self, Button.ZR, is_rectangular=True)
        self.btn_home = ControllerButton("🏠", self, Button.HOME)
        self.btn_plus = ControllerButton("+", self, Button.PLUS)
        self.btn_x = ControllerButton("X", self, Button.X)
        self.btn_y = ControllerButton("Y", self, Button.Y)
        self.btn_a = ControllerButton("A", self, Button.A)
        self.btn_b = ControllerButton("B", self, Button.B)
        self.right_stick = AnalogStick(self, is_left=False)
        self.btn_rs = ControllerButton("RS", self, Button.RS, is_rectangular=True)

    def _connect_buttons(self) -> None:
        for btn in [
            self.btn_a,
            self.btn_b,
            self.btn_x,
            self.btn_y,
            self.btn_l,
            self.btn_r,
            self.btn_zl,
            self.btn_zr,
            self.btn_minus,
            self.btn_plus,
            self.btn_home,
            self.btn_capture,
            self.btn_ls,
            self.btn_rs,
        ]:
            btn.pressed.connect(lambda b=btn: self.model.button_press(b.button_type))
            btn.released.connect(lambda b=btn: self.model.button_release(b.button_type))
        self.left_stick.valueChanged.connect(self.model.set_left_stick)
        self.right_stick.valueChanged.connect(self.model.set_right_stick)
        self.dpad.directionChanged.connect(self.model.set_hat_direction)

    def apply_layout_size(self, width: int, height: int) -> None:
        self._layout_size = QSize(width, height)
        self.setFixedSize(width, height)
        scale = min(width / _BASE_WIDTH, height / _BASE_HEIGHT)
        content_width = round(_BASE_WIDTH * scale)
        content_height = round(_BASE_HEIGHT * scale)
        offset_x = (width - content_width) // 2
        offset_y = (height - content_height) // 2
        font_size = max(8, round(9 * scale))

        for name, base_rect in _BASE_RECTS.items():
            rect = self._scaled_rect(base_rect, scale, offset_x, offset_y, width, height)
            widget = getattr(self, name)
            if isinstance(widget, AnalogStick):
                widget.set_diameter(rect.width())
            elif isinstance(widget, DPad):
                widget.set_diameter(rect.width())
            elif isinstance(widget, ControllerButton):
                widget.configure_size(
                    (rect.width(), rect.height()),
                    radius=min(rect.width(), rect.height()) // 2,
                    font_size=font_size,
                )
            widget.setGeometry(rect)

    def sizeHint(self) -> QSize:
        return self._layout_size

    def minimumSizeHint(self) -> QSize:
        return self._layout_size

    def _scaled_rect(
        self,
        base_rect: _WidgetRect,
        scale: float,
        offset_x: int,
        offset_y: int,
        canvas_width: int,
        canvas_height: int,
    ) -> QRect:
        width = max(1, round(base_rect.width * scale))
        height = max(1, round(base_rect.height * scale))
        x = offset_x + round(base_rect.x * scale)
        y = offset_y + round(base_rect.y * scale)
        if x + width > canvas_width:
            x = canvas_width - width
        if y + height > canvas_height:
            y = canvas_height - height
        return QRect(max(0, x), max(0, y), width, height)
