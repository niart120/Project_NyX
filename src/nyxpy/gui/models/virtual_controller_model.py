from PySide6.QtCore import QObject, Signal

from nyxpy.framework.core.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.io.ports import ControllerOutputPort
from nyxpy.framework.core.logger import LoggerPort


class VirtualControllerModel(QObject):
    """仮想コントローラーの状態管理と controller port への出力を担当するモデル。"""

    # 状態変更通知用シグナル
    stateChanged = Signal()

    def __init__(
        self,
        logger: LoggerPort,
        controller: ControllerOutputPort | None = None,
    ) -> None:
        super().__init__()
        self.logger = logger
        self.controller = controller

        # コントローラー状態
        self.pressed_buttons: set[Button] = set()
        self.current_hat: Hat = Hat.CENTER
        self.current_l_stick: LStick = LStick.CENTER
        self.current_r_stick: RStick = RStick.CENTER

    def set_controller(self, controller: ControllerOutputPort | None) -> None:
        """コントローラー出力 Port を設定"""
        self.controller = controller

    def button_press(self, button: Button) -> None:
        """ボタンが押されたときの処理"""
        self.pressed_buttons.add(button)
        # ボタン押下の専用コマンドを送信
        self.send_press_command((button,))

    def button_release(self, button: Button) -> None:
        """ボタンが離されたときの処理"""
        if button in self.pressed_buttons:
            self.pressed_buttons.remove(button)
            # ボタン解放の専用コマンドを送信
            self.send_release_command((button,))

    def set_hat_direction(self, direction: Hat) -> None:
        """方向パッドの方向を設定"""
        previous_direction = self.current_hat
        self.current_hat = direction

        # CENTERに戻る場合は解放コマンドを送信
        if direction == Hat.CENTER and previous_direction != Hat.CENTER:
            self.send_release_command((previous_direction,))
        # それ以外の場合は押下コマンドを送信
        else:
            self.send_press_command((direction,))

    def set_left_stick(self, angle: float, strength: float) -> None:
        """左スティックの状態を設定"""
        previous_stick = self.current_l_stick

        # スティックの強度が0.1以上の場合、スティックを押下状態にする
        # それ以外の場合はスティックを中央に戻す
        if strength > 0.1:
            self.current_l_stick = LStick(angle, strength)
            self.send_press_command((self.current_l_stick,))
        else:
            # スティックを戻す場合、以前の状態が中央でなければ解放コマンドを送信
            if previous_stick != LStick.CENTER:
                self.send_release_command((previous_stick,))
            self.current_l_stick = LStick.CENTER

    def set_right_stick(self, angle: float, strength: float) -> None:
        """右スティックの状態を設定"""
        previous_stick = self.current_r_stick

        # スティックの強度が0.1以上の場合、スティックを押下状態にする
        # それ以外の場合はスティックを中央に戻す
        if strength > 0.1:
            self.current_r_stick = RStick(angle, strength)
            self.send_press_command((self.current_r_stick,))
        else:
            # スティックを戻す場合、以前の状態が中央でなければ解放コマンドを送信
            if previous_stick != RStick.CENTER:
                self.send_release_command((previous_stick,))
            self.current_r_stick = RStick.CENTER

    def send_release_command(self, keys: tuple[Button | Hat | LStick | RStick, ...]) -> None:
        if self.controller is None:
            return
        try:
            self.controller.release(keys)
        except Exception as e:
            self.logger.technical(
                "ERROR",
                "コントローラー解放コマンド送信エラー",
                component="VirtualController",
                event="controller.release_failed",
                exc=e,
            )
            raise

    def send_press_command(self, keys: tuple[Button | Hat | LStick | RStick, ...]) -> None:
        if self.controller is None:
            return
        try:
            self.controller.press(keys)
        except Exception as e:
            self.logger.technical(
                "ERROR",
                "コントローラー押下コマンド送信エラー",
                component="VirtualController",
                event="controller.press_failed",
                exc=e,
            )
            raise
