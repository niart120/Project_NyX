
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from nyxpy.framework.core.constants import Button
from nyxpy.gui.models.virtual_controller_model import VirtualControllerModel
from nyxpy.gui.widgets.controller.analog_stick import AnalogStick
from nyxpy.gui.widgets.controller.button import ControllerButton
from nyxpy.gui.widgets.controller.dpad import DPad


class VirtualControllerPane(QWidget):
    """仮想コントローラーのメインペイン"""

    def __init__(
        self, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.model = VirtualControllerModel()
        self.initUI()

    def initUI(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)

        # メインコントローラーレイアウト
        controller_layout = QHBoxLayout()
        controller_layout.setSpacing(5)

        # 左側のレイアウト
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)

        # 左トリガーボタン (ZL, L)
        trigger_layout_left = QHBoxLayout()
        trigger_layout_left.setSpacing(2)

        # 外側にZLを配置
        self.btn_zl = ControllerButton(
            "ZL", self, Button.ZL, size=(30, 20), is_rectangular=True
        )
        self.btn_l = ControllerButton(
            "L", self, Button.L, size=(30, 20), is_rectangular=True
        )

        trigger_layout_left.addWidget(self.btn_zl)
        trigger_layout_left.addWidget(self.btn_l)
        left_layout.addLayout(trigger_layout_left)

        # ボタンを横に一列配置 (-, Capture) - 右寄せに配置
        system_layout_left = QHBoxLayout()
        system_layout_left.setAlignment(Qt.AlignRight)  # 右寄せに設定
        system_layout_left.setSpacing(4)

        self.btn_minus = ControllerButton(
            "-", self, Button.MINUS, size=(35, 25), radius=12
        )
        self.btn_capture = ControllerButton(
            "📷", self, Button.CAP, size=(35, 25), radius=12
        )

        system_layout_left.addWidget(self.btn_minus)
        system_layout_left.addWidget(self.btn_capture)

        left_layout.addLayout(system_layout_left)

        # 左側のメインコントロール (左スティックと方向パッド)
        left_main_layout = QHBoxLayout()

        # 左スティックと押し込みボタン
        left_stick_container = QVBoxLayout()
        left_stick_container.setSpacing(2)

        self.left_stick = AnalogStick(self, is_left=True)
        self.left_stick.valueChanged.connect(self.model.set_left_stick)

        # LS（左スティック押し込み）ボタン
        self.btn_ls = ControllerButton(
            "LS", self, Button.LS, size=(30, 20), is_rectangular=True
        )

        left_stick_container.addWidget(self.left_stick, alignment=Qt.AlignCenter)
        left_stick_container.addWidget(self.btn_ls, alignment=Qt.AlignCenter)

        # 方向パッド
        self.dpad = DPad(self)
        self.dpad.directionChanged.connect(self.model.set_hat_direction)

        left_main_layout.addLayout(left_stick_container)
        left_main_layout.addWidget(self.dpad)

        left_layout.addLayout(left_main_layout)

        controller_layout.addLayout(left_layout)

        # 右側のレイアウト
        right_layout = QVBoxLayout()
        right_layout.setSpacing(2)

        # 右トリガーボタン (R, ZR)
        trigger_layout_right = QHBoxLayout()
        trigger_layout_right.setSpacing(2)

        # 外側にZRを配置
        self.btn_r = ControllerButton(
            "R", self, Button.R, size=(30, 20), is_rectangular=True
        )
        self.btn_zr = ControllerButton(
            "ZR", self, Button.ZR, size=(30, 20), is_rectangular=True
        )

        trigger_layout_right.addWidget(self.btn_r)
        trigger_layout_right.addWidget(self.btn_zr)
        right_layout.addLayout(trigger_layout_right)

        # 右側のメインコントロール (A/B/X/Y ボタンと右スティック)
        right_main_layout = QHBoxLayout()

        # ボタンを横に一列配置 (Home, +) - 左寄せに配置
        system_layout_right = QHBoxLayout()
        system_layout_right.setAlignment(Qt.AlignLeft)  # 左寄せに設定
        system_layout_right.setSpacing(4)

        self.btn_home = ControllerButton(
            "🏠", self, Button.HOME, size=(35, 25), radius=12
        )
        self.btn_plus = ControllerButton(
            "+", self, Button.PLUS, size=(35, 25), radius=12
        )

        system_layout_right.addWidget(self.btn_home)
        system_layout_right.addWidget(self.btn_plus)

        right_layout.addLayout(system_layout_right)

        # A/B/X/Y ボタン
        button_grid = QGridLayout()
        button_grid.setSpacing(2)

        self.btn_x = ControllerButton("X", self, Button.X, size=(25, 25), radius=12)
        self.btn_y = ControllerButton("Y", self, Button.Y, size=(25, 25), radius=12)
        self.btn_a = ControllerButton("A", self, Button.A, size=(25, 25), radius=12)
        self.btn_b = ControllerButton("B", self, Button.B, size=(25, 25), radius=12)

        button_grid.addWidget(self.btn_y, 1, 0)
        button_grid.addWidget(self.btn_x, 0, 1)
        button_grid.addWidget(self.btn_b, 2, 1)
        button_grid.addWidget(self.btn_a, 1, 2)

        # 右スティックと押し込みボタン
        right_stick_container = QVBoxLayout()
        right_stick_container.setSpacing(2)

        self.right_stick = AnalogStick(self, is_left=False)
        self.right_stick.valueChanged.connect(self.model.set_right_stick)

        # RS（右スティック押し込み）ボタン
        self.btn_rs = ControllerButton(
            "RS", self, Button.RS, size=(30, 20), is_rectangular=True
        )

        right_stick_container.addWidget(self.right_stick, alignment=Qt.AlignCenter)
        right_stick_container.addWidget(self.btn_rs, alignment=Qt.AlignCenter)

        right_main_layout.addLayout(button_grid)
        right_main_layout.addLayout(right_stick_container)

        right_layout.addLayout(right_main_layout)

        controller_layout.addLayout(right_layout)

        main_layout.addLayout(controller_layout)

        # ボタンを押した時のイベント設定
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
