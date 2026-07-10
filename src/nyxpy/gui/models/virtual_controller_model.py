"""Virtual controller 表示用 model。"""

from PySide6.QtCore import QObject, Signal

from nyxpy.framework.core.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.io.ports import ControllerOutputPort
from nyxpy.framework.core.logger import LoggerPort


class VirtualControllerModel(QObject):
    """仮想コントローラーの状態管理と controller port への出力を担当するモデル。"""

    # 状態変更通知用シグナル
    stateChanged = Signal()
    inputFailed = Signal(object, object)

    def __init__(
        self,
        logger: LoggerPort,
        controller: ControllerOutputPort | None = None,
    ) -> None:
        """Logger と controller port を保持し、仮想 controller 状態を初期化します。"""
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.manual_input_enabled = controller is not None

        # コントローラー状態
        self.pressed_buttons: set[Button] = set()
        self.current_hat: Hat = Hat.CENTER
        self.current_l_stick: LStick = LStick.CENTER
        self.current_r_stick: RStick = RStick.CENTER

    def set_controller(self, controller: ControllerOutputPort | None) -> None:
        """コントローラー出力 Port を設定"""
        self.controller = controller

    def set_manual_input_enabled(self, enabled: bool) -> None:
        """Manual input の有効状態を切り替える。"""
        self.manual_input_enabled = bool(enabled and self.controller is not None)
        self.stateChanged.emit()

    def reset_state(self) -> None:
        """GUI が保持する入力表示状態を neutral に戻す。"""
        self.pressed_buttons.clear()
        self.current_hat = Hat.CENTER
        self.current_l_stick = LStick.CENTER
        self.current_r_stick = RStick.CENTER
        self.stateChanged.emit()

    def supports_touch_input(self) -> bool:
        return (
            self.manual_input_enabled
            and self.controller is not None
            and self.controller.supports_touch
        )

    def button_press(self, button: Button) -> None:
        """ボタンが押されたときの処理"""
        if not self._can_send_input():
            return
        if self.send_press_command((button,)):
            self.pressed_buttons.add(button)

    def button_release(self, button: Button) -> None:
        """ボタンが離されたときの処理"""
        if not self._can_send_input():
            return
        if button in self.pressed_buttons and self.send_release_command((button,)):
            self.pressed_buttons.remove(button)

    def set_hat_direction(self, direction: Hat) -> None:
        """方向パッドの方向を設定"""
        if not self._can_send_input():
            return
        previous_direction = self.current_hat
        if direction == Hat.CENTER and previous_direction != Hat.CENTER:
            sent = self.send_release_command((previous_direction,))
        else:
            sent = self.send_press_command((direction,))
        if sent:
            self.current_hat = direction

    def set_left_stick(self, angle: float, strength: float) -> None:
        """左スティックの状態を設定"""
        if not self._can_send_input():
            return
        previous_stick = self.current_l_stick

        # スティックの強度が0.1以上の場合、スティックを押下状態にする
        # それ以外の場合はスティックを中央に戻す
        if strength > 0.1:
            next_stick = LStick(angle, strength)
            if self.send_press_command((next_stick,)):
                self.current_l_stick = next_stick
        else:
            if previous_stick == LStick.CENTER or self.send_release_command((previous_stick,)):
                self.current_l_stick = LStick.CENTER

    def set_right_stick(self, angle: float, strength: float) -> None:
        """右スティックの状態を設定"""
        if not self._can_send_input():
            return
        previous_stick = self.current_r_stick

        # スティックの強度が0.1以上の場合、スティックを押下状態にする
        # それ以外の場合はスティックを中央に戻す
        if strength > 0.1:
            next_stick = RStick(angle, strength)
            if self.send_press_command((next_stick,)):
                self.current_r_stick = next_stick
        else:
            if previous_stick == RStick.CENTER or self.send_release_command((previous_stick,)):
                self.current_r_stick = RStick.CENTER

    def touch_down(self, x: int, y: int) -> None:
        controller = self.controller
        if not self.manual_input_enabled or controller is None or not controller.supports_touch:
            return
        try:
            controller.touch_down(x, y)
        except Exception as e:
            self._handle_input_failure(
                e,
                controller,
                message="タッチ押下コマンド送信エラー",
                event="controller.touch_down_failed",
            )

    def touch_move(self, x: int, y: int) -> None:
        self.touch_down(x, y)

    def touch_up(self) -> None:
        controller = self.controller
        if not self.manual_input_enabled or controller is None or not controller.supports_touch:
            return
        try:
            controller.touch_up()
        except Exception as e:
            self._handle_input_failure(
                e,
                controller,
                message="タッチ解放コマンド送信エラー",
                event="controller.touch_up_failed",
            )

    def send_release_command(self, keys: tuple[Button | Hat | LStick | RStick, ...]) -> bool:
        controller = self.controller
        if not self.manual_input_enabled or controller is None:
            return False
        try:
            controller.release(keys)
        except Exception as e:
            self._handle_input_failure(
                e,
                controller,
                message="コントローラー解放コマンド送信エラー",
                event="controller.release_failed",
            )
            return False
        return True

    def send_press_command(self, keys: tuple[Button | Hat | LStick | RStick, ...]) -> bool:
        controller = self.controller
        if not self.manual_input_enabled or controller is None:
            return False
        try:
            controller.press(keys)
        except Exception as e:
            self._handle_input_failure(
                e,
                controller,
                message="コントローラー押下コマンド送信エラー",
                event="controller.press_failed",
            )
            return False
        return True

    def release_all(self) -> None:
        """Manual input の保持状態を解除し、controller へ全解除を送る。"""
        self.reset_state()
        self.send_release_command(())

    def _can_send_input(self) -> bool:
        return self.manual_input_enabled and self.controller is not None

    def _handle_input_failure(
        self,
        error: Exception,
        controller: ControllerOutputPort,
        *,
        message: str,
        event: str,
    ) -> None:
        self.logger.technical(
            "ERROR",
            message,
            component="VirtualController",
            event=event,
            exc=error,
        )
        if self.controller is controller:
            self.controller = None
        self.manual_input_enabled = False
        self.reset_state()
        self.inputFailed.emit(error, controller)
