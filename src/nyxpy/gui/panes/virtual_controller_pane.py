from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush, QPaintEvent, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QHBoxLayout, QSizePolicy

import math
from nyxpy.framework.core.macro.constants import Button, Hat, LStick, RStick, KeyType
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol
from nyxpy.framework.core.hardware.facade import HardwareFacade
from nyxpy.framework.core.logger.log_manager import log_manager


class ControllerButton(QPushButton):
    """カスタムスタイルのコントローラーボタン"""
    def __init__(self, text="", parent=None, button_type=None, size=(30, 30), radius=15, is_rectangular=False):
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


class AnalogStick(QWidget):
    """アナログスティックウィジェット"""
    valueChanged = Signal(float, float)  # 角度と強さのシグナル
    
    def __init__(self, parent=None, is_left=True):
        super().__init__(parent)
        self.is_left = is_left
        self.setFixedSize(60, 60)
        self.position = QPointF(30, 30)  # 中央位置
        self.dragging = False
        self.setMouseTracking(True)
        
        # スティックの色
        self.stick_color = QColor(0, 120, 215) if is_left else QColor(215, 0, 0)
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # ベース円の描画
        base_rect = QRectF(5, 5, 50, 50)
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        painter.drawEllipse(base_rect)
        
        # スティックの描画
        stick_rect = QRectF(self.position.x() - 10, self.position.y() - 10, 20, 20)
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.setBrush(QBrush(self.stick_color))
        painter.drawEllipse(stick_rect)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.updateStickPosition(event.pos())
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging:
            self.updateStickPosition(event.pos())
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            # スティックを中央に戻す
            self.position = QPointF(30, 30)
            self.update()
            self.valueChanged.emit(0, 0)  # 角度0、強さ0を送信
    
    def updateStickPosition(self, pos):
        # スティック範囲内に収める
        center = QPointF(30, 30)
        vector = QPointF(pos.x() - center.x(), pos.y() - center.y())
        
        # 距離を計算
        distance = math.sqrt(vector.x() * vector.x() + vector.y() * vector.y())
        max_distance = 20
        
        # 最大範囲に制限
        if distance > max_distance:
            vector = vector * (max_distance / distance)
        
        self.position = QPointF(center.x() + vector.x(), center.y() + vector.y())
        
        # 角度と強さを計算してシグナル発信
        if distance > 0:
            angle = math.atan2(vector.y(), vector.x())
            strength = min(1.0, distance / max_distance)
            # Switch のスティックと同じ座標系に変換
            switch_angle = (-angle) % (2 * math.pi)
            self.valueChanged.emit(switch_angle, strength)
        else:
            self.valueChanged.emit(0, 0)
        
        self.update()


class DPad(QWidget):
    """方向パッド（十字キー）ウィジェット"""
    directionChanged = Signal(Hat)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.current_direction = Hat.CENTER
        self.pressed = False
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 基本の十字形を描画
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        
        # 中央円
        painter.drawEllipse(27, 27, 16, 16)
        
        # 上方向
        up_path = QPainterPath()
        up_path.addRoundedRect(27, 5, 16, 25, 5, 5)
        
        # 右方向
        right_path = QPainterPath()
        right_path.addRoundedRect(40, 27, 25, 16, 5, 5)
        
        # 下方向
        down_path = QPainterPath()
        down_path.addRoundedRect(27, 40, 16, 25, 5, 5)
        
        # 左方向
        left_path = QPainterPath()
        left_path.addRoundedRect(5, 27, 25, 16, 5, 5)
        
        # 押されている方向の色を変更
        if self.current_direction != Hat.CENTER:
            painter.setBrush(QBrush(QColor(100, 100, 100)))
            
            if self.current_direction in (Hat.UP, Hat.UPRIGHT, Hat.UPLEFT):
                painter.drawPath(up_path)
            
            if self.current_direction in (Hat.RIGHT, Hat.UPRIGHT, Hat.DOWNRIGHT):
                painter.drawPath(right_path)
            
            if self.current_direction in (Hat.DOWN, Hat.DOWNRIGHT, Hat.DOWNLEFT):
                painter.drawPath(down_path)
            
            if self.current_direction in (Hat.LEFT, Hat.UPLEFT, Hat.DOWNLEFT):
                painter.drawPath(left_path)
            
            # 残りの方向は通常色で描画
            painter.setBrush(QBrush(QColor(60, 60, 60)))
        
        # 通常色でパスを描画
        if self.current_direction not in (Hat.UP, Hat.UPRIGHT, Hat.UPLEFT):
            painter.drawPath(up_path)
        
        if self.current_direction not in (Hat.RIGHT, Hat.UPRIGHT, Hat.DOWNRIGHT):
            painter.drawPath(right_path)
        
        if self.current_direction not in (Hat.DOWN, Hat.DOWNRIGHT, Hat.DOWNLEFT):
            painter.drawPath(down_path)
        
        if self.current_direction not in (Hat.LEFT, Hat.UPLEFT, Hat.DOWNLEFT):
            painter.drawPath(left_path)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            self.updateDirection(event.pos())
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.pressed:
            self.updateDirection(event.pos())
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.pressed:
            self.pressed = False
            self.current_direction = Hat.CENTER
            self.update()
            self.directionChanged.emit(Hat.CENTER)
    
    def updateDirection(self, pos):
        center_x, center_y = 35, 35
        x, y = pos.x() - center_x, pos.y() - center_y
        
        # 押された位置に基づいて方向を判定
        if abs(x) < 8 and abs(y) < 8:  # 中央エリア
            direction = Hat.CENTER
        else:
            angle = math.atan2(y, x)
            angle_deg = math.degrees(angle)
            
            # 角度から方向を判定
            if angle_deg < -157.5 or angle_deg >= 157.5:
                direction = Hat.LEFT
            elif -157.5 <= angle_deg < -112.5:
                direction = Hat.UPLEFT
            elif -112.5 <= angle_deg < -67.5:
                direction = Hat.UP
            elif -67.5 <= angle_deg < -22.5:
                direction = Hat.UPRIGHT
            elif -22.5 <= angle_deg < 22.5:
                direction = Hat.RIGHT
            elif 22.5 <= angle_deg < 67.5:
                direction = Hat.DOWNRIGHT
            elif 67.5 <= angle_deg < 112.5:
                direction = Hat.DOWN
            else:  # 112.5 <= angle_deg < 157.5
                direction = Hat.DOWNLEFT
        
        if self.current_direction != direction:
            self.current_direction = direction
            self.update()
            self.directionChanged.emit(direction)


class VirtualControllerPane(QWidget):
    """仮想コントローラーのメインペイン"""
    
    def __init__(self, parent=None, serial_manager=None):
        super().__init__(parent)
        self.serial_manager = serial_manager
        self.protocol = CH552SerialProtocol()
        self.pressed_buttons = set()
        self.current_hat = Hat.CENTER
        self.current_l_stick = LStick.CENTER
        self.current_r_stick = RStick.CENTER
        
        self.initUI()
    
    def initUI(self):
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
        self.btn_zl = ControllerButton("ZL", self, Button.ZL, size=(30, 20), is_rectangular=True)
        self.btn_l = ControllerButton("L", self, Button.L, size=(30, 20), is_rectangular=True)
        
        trigger_layout_left.addWidget(self.btn_zl)
        trigger_layout_left.addWidget(self.btn_l)
        left_layout.addLayout(trigger_layout_left)

        # ボタンを横に一列配置 (-, Capture)
        system_layout_left = QHBoxLayout()
        
        self.btn_minus = ControllerButton("-", self, Button.MINUS, size=(35, 25), radius=12)
        self.btn_capture = ControllerButton("CAP", self, Button.CAP, size=(35, 25), radius=12)
        
        system_layout_left.addWidget(self.btn_minus)
        system_layout_left.addWidget(self.btn_capture)
        
        left_layout.addLayout(system_layout_left)
        
        controller_layout.addLayout(left_layout)
        
        # 左側のメインコントロール (左スティックと方向パッド)
        left_main_layout = QHBoxLayout()
        
        # 左スティックと押し込みボタン
        left_stick_container = QVBoxLayout()
        left_stick_container.setSpacing(2)
        
        self.left_stick = AnalogStick(self, is_left=True)
        self.left_stick.valueChanged.connect(self.onLeftStickChanged)
        
        # LS（左スティック押し込み）ボタン
        self.btn_ls = ControllerButton("LS", self, Button.LS, size=(30, 20), is_rectangular=True)
        
        left_stick_container.addWidget(self.left_stick, alignment=Qt.AlignCenter)
        left_stick_container.addWidget(self.btn_ls, alignment=Qt.AlignCenter)
        
        # 方向パッド
        self.dpad = DPad(self)
        self.dpad.directionChanged.connect(self.onDPadChanged)
        
        left_main_layout.addLayout(left_stick_container)
        left_main_layout.addWidget(self.dpad)
        
        left_layout.addLayout(left_main_layout)

        
        # 右側のレイアウト
        right_layout = QVBoxLayout()
        right_layout.setSpacing(2)
        
        # 右トリガーボタン (R, ZR)
        trigger_layout_right = QHBoxLayout()
        trigger_layout_right.setSpacing(2)
        
        # 外側にZRを配置
        self.btn_r = ControllerButton("R", self, Button.R, size=(30, 20), is_rectangular=True)
        self.btn_zr = ControllerButton("ZR", self, Button.ZR, size=(30, 20), is_rectangular=True)
        
        trigger_layout_right.addWidget(self.btn_r)
        trigger_layout_right.addWidget(self.btn_zr)
        right_layout.addLayout(trigger_layout_right)

        # ボタンを横に一列配置 (Home, +)
        system_layout_right = QHBoxLayout()
        
        self.btn_home = ControllerButton("H", self, Button.HOME, size=(35, 25), radius=12)
        self.btn_plus = ControllerButton("+", self, Button.PLUS, size=(35, 25), radius=12)
        
        system_layout_right.addWidget(self.btn_home)
        system_layout_right.addWidget(self.btn_plus)
        
        right_layout.addLayout(system_layout_right)
        
        # 右側のメインコントロール (A/B/X/Y ボタンと右スティック)
        right_main_layout = QHBoxLayout()
        
        # A/B/X/Y ボタン
        button_grid = QGridLayout()
        button_grid.setSpacing(2)
        
        self.btn_x = ControllerButton("X", self, Button.X, size=(25, 25), radius=12)
        self.btn_y = ControllerButton("Y", self, Button.Y, size=(25, 25), radius=12)
        self.btn_a = ControllerButton("A", self, Button.A, size=(25, 25), radius=12)
        self.btn_b = ControllerButton("B", self, Button.B, size=(25, 25), radius=12)
        
        button_grid.addWidget(self.btn_y, 0, 1)
        button_grid.addWidget(self.btn_x, 1, 0)
        button_grid.addWidget(self.btn_b, 1, 2)
        button_grid.addWidget(self.btn_a, 2, 1)
        
        # 右スティックと押し込みボタン
        right_stick_container = QVBoxLayout()
        right_stick_container.setSpacing(2)
        
        self.right_stick = AnalogStick(self, is_left=False)
        self.right_stick.valueChanged.connect(self.onRightStickChanged)
        
        # RS（右スティック押し込み）ボタン
        self.btn_rs = ControllerButton("RS", self, Button.RS, size=(30, 20), is_rectangular=True)
        
        right_stick_container.addWidget(self.right_stick, alignment=Qt.AlignCenter)
        right_stick_container.addWidget(self.btn_rs, alignment=Qt.AlignCenter)
        
        right_main_layout.addLayout(button_grid)
        right_main_layout.addLayout(right_stick_container)
        
        right_layout.addLayout(right_main_layout)
    
        
        controller_layout.addLayout(right_layout)
        
        main_layout.addLayout(controller_layout)
        
        # ボタンを押した時のイベント設定
        for btn in [self.btn_a, self.btn_b, self.btn_x, self.btn_y, 
                   self.btn_l, self.btn_r, self.btn_zl, self.btn_zr,
                   self.btn_minus, self.btn_plus, self.btn_home, self.btn_capture,
                   self.btn_ls, self.btn_rs]:
            btn.pressed.connect(lambda b=btn: self.onButtonPressed(b.button_type))
            btn.released.connect(lambda b=btn: self.onButtonReleased(b.button_type))
    
    def onButtonPressed(self, button):
        self.pressed_buttons.add(button)
        self.sendControllerState()
    
    def onButtonReleased(self, button):
        if button in self.pressed_buttons:
            self.pressed_buttons.remove(button)
        self.sendControllerState()
    
    def onDPadChanged(self, direction):
        self.current_hat = direction
        self.sendControllerState()
    
    def onLeftStickChanged(self, angle, strength):
        if strength > 0:
            self.current_l_stick = LStick(angle, strength)
        else:
            self.current_l_stick = LStick.CENTER
        self.sendControllerState()
    
    def onRightStickChanged(self, angle, strength):
        if strength > 0:
            self.current_r_stick = RStick(angle, strength)
        else:
            self.current_r_stick = RStick.CENTER
        self.sendControllerState()
    
    def sendControllerState(self):
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