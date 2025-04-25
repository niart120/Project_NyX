from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.logger.log_manager import log_manager
from PySide6.QtCore import QObject, Signal
from typing import Optional, Set, Union


class VirtualControllerModel(QObject):
    """仮想コントローラーの状態管理とシリアル通信を担当するモデルクラス"""
    
    # 状態変更通知用シグナル
    stateChanged = Signal()
    
    def __init__(
        self,
        serial_manager: Optional[SerialManager] = None,
        protocol: Optional[SerialProtocolInterface] = None,
    ) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        # デフォルトでCH552プロトコルを使用（外部から変更される想定）
        self.protocol = protocol or ProtocolFactory.create_protocol("CH552")
        
        # コントローラー状態
        self.pressed_buttons: Set[Button] = set()
        self.current_hat: Hat = Hat.CENTER
        self.current_l_stick: LStick = LStick.CENTER
        self.current_r_stick: RStick = RStick.CENTER
    
    def set_serial_manager(self, serial_manager: SerialManager) -> None:
        """シリアルマネージャーを設定"""
        self.serial_manager = serial_manager
    
    def set_protocol(self, protocol: SerialProtocolInterface) -> None:
        """シリアルプロトコルを設定"""
        self.protocol = protocol
        # プロトコルが変更されたことをログに記録
        log_manager.log("INFO", f"仮想コントローラーのプロトコルを変更: {protocol.__class__.__name__}", "VirtualController")
        
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
    
    def send_release_command(self, keys: tuple[Union[Button, Hat, LStick, RStick], ...]) -> None:
        """特定のキーの解放コマンドをシリアルデバイスに送信"""
        if not self.serial_manager or not self.serial_manager.is_active():
            return
            
        try:
            command_data = self.protocol.build_release_command(keys)
            self.serial_manager.get_active_device().send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラー解放コマンド送信エラー: {e}", "VirtualController")
            raise e
    
    def send_press_command(self, keys: tuple[Union[Button, Hat, LStick, RStick], ...]) -> None:
        """特定のキーの押下コマンドをシリアルデバイスに送信"""
        if not self.serial_manager or not self.serial_manager.is_active():
            return
            
        try:
            command_data = self.protocol.build_press_command(keys)
            self.serial_manager.get_active_device().send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラー押下コマンド送信エラー: {e}", "VirtualController")
            raise e
