from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPaintEvent, QMouseEvent
from PySide6.QtWidgets import QWidget
import math
from nyxpy.framework.core.macro.constants import LStick, RStick

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