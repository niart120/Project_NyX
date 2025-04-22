from nyxpy.framework.core.macro.constants import Button, Hat, LStick, RStick
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.logger.log_manager import log_manager
from PySide6.QtCore import QObject, Signal


class VirtualControllerModel(QObject):
    """仮想コントローラーの状態管理とシリアル通信を担当するモデルクラス"""
    
    # 状態変更通知用シグナル
    stateChanged = Signal()
    
    def __init__(self, serial_manager=None):
        super().__init__()
        self.serial_manager = serial_manager
        self.protocol = CH552SerialProtocol()
        
        # コントローラー状態
        self.pressed_buttons = set()
        self.current_hat = Hat.CENTER
        self.current_l_stick = LStick.CENTER
        self.current_r_stick = RStick.CENTER
    
    def set_serial_manager(self, serial_manager):
        """シリアルマネージャーを設定"""
        self.serial_manager = serial_manager
        
    def button_press(self, button):
        """ボタンが押されたときの処理"""
        self.pressed_buttons.add(button)
        self.send_controller_state()
        
    def button_release(self, button):
        """ボタンが離されたときの処理"""
        if button in self.pressed_buttons:
            self.pressed_buttons.remove(button)
        self.send_controller_state()
        
    def set_hat_direction(self, direction):
        """方向パッドの方向を設定"""
        self.current_hat = direction
        self.send_controller_state()
        
    def set_left_stick(self, angle, strength):
        """左スティックの状態を設定"""
        if strength > 0:
            self.current_l_stick = LStick(angle, strength)
        else:
            self.current_l_stick = LStick.CENTER
        self.send_controller_state()
        
    def set_right_stick(self, angle, strength):
        """右スティックの状態を設定"""
        if strength > 0:
            self.current_r_stick = RStick(angle, strength)
        else:
            self.current_r_stick = RStick.CENTER
        self.send_controller_state()
        
    def send_controller_state(self):
        """現在のコントローラ状態をシリアルデバイスに送信"""
        if not self.serial_manager or not self.serial_manager.is_active():
            return
        
        # 入力キーのリストを作成
        keys = list(self.pressed_buttons)
        
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
            self.serial_manager.send(command_data)
        except Exception as e:
            log_manager.log("ERROR", f"コントローラーコマンド送信エラー: {e}", "VirtualController")
        
        # 状態変更を通知
        self.stateChanged.emit()