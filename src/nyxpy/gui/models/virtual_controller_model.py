from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.macro.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol, SerialProtocolInterface
from nyxpy.framework.core.logger.log_manager import log_manager
from PySide6.QtCore import QObject, Signal
from typing import Optional, Set, List, Union


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
        self.protocol = protocol or CH552SerialProtocol()
        
        # コントローラー状態
        self.pressed_buttons: Set[Button] = set()
        self.current_hat: Hat = Hat.CENTER
        self.current_l_stick: LStick = LStick.CENTER
        self.current_r_stick: RStick = RStick.CENTER
    
    def set_serial_manager(self, serial_manager: SerialManager) -> None:
        """シリアルマネージャーを設定"""
        self.serial_manager = serial_manager
    
    def set_SerialProtocol(self, protocol: SerialProtocolInterface) -> None:
        """シリアルプロトコルを設定"""
        self.protocol = protocol
        
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
        self.current_hat = direction
        self.update_controller_state()
        
    def set_left_stick(self, angle: float, strength: float) -> None:
        """左スティックの状態を設定"""
        if strength > 0:
            self.current_l_stick = LStick(angle, strength)
        else:
            self.current_l_stick = LStick.CENTER
        self.update_controller_state()
        
    def set_right_stick(self, angle: float, strength: float) -> None:
        """右スティックの状態を設定"""
        if strength > 0:
            self.current_r_stick = RStick(angle, strength)
        else:
            self.current_r_stick = RStick.CENTER
        self.update_controller_state()
        
    def send_release_command(self, keys: tuple[Union[Button, Hat, LStick, RStick], ...]) -> None:
        """特定のキーの解放コマンドをシリアルデバイスに送信"""
        if not self.serial_manager or not self.serial_manager.is_active():
            return
            
        try:
            command_data = self.protocol.build_release_command(keys)
            self.serial_manager.get_active_device().send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラー解放コマンド送信エラー: {e}", "VirtualController")
    
    def send_press_command(self, keys: tuple[Union[Button, Hat, LStick, RStick], ...]) -> None:
        """特定のキーの押下コマンドをシリアルデバイスに送信"""
        if not self.serial_manager or not self.serial_manager.is_active():
            return
            
        try:
            command_data = self.protocol.build_press_command(keys)
            self.serial_manager.get_active_device().send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラー押下コマンド送信エラー: {e}", "VirtualController")
    
    def update_controller_state(self) -> None:
        """現在のコントローラ状態をシリアルデバイスに送信する
        
        内部状態に保持されている全ての入力（ボタン、方向パッド、スティック）を
        まとめてプレスコマンドとして生成・送信します。
        """
        if not self.serial_manager or not self.serial_manager.is_active():
            return
        
        # 入力キーのリストを作成
        keys: List[Union[Button, Hat, LStick, RStick]] = list(self.pressed_buttons)
        
        # 方向パッド
        if self.current_hat != Hat.CENTER:
            keys.append(self.current_hat)
            
        # 左右スティック
        if self.current_l_stick != LStick.CENTER:
            keys.append(self.current_l_stick)
        if self.current_r_stick != RStick.CENTER:
            keys.append(self.current_r_stick)
        
        # プレスコマンドを生成
        try:
            command_data = self.protocol.build_press_command(tuple(keys))
            self.serial_manager.get_active_device().send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラー状態更新エラー: {e}", "VirtualController")
        
        # 状態変更を通知
        self.stateChanged.emit()
