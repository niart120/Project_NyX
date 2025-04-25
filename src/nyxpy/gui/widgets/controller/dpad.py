from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush, QPaintEvent, QMouseEvent
from PySide6.QtWidgets import QWidget
from typing import Optional
import math
from nyxpy.framework.core.constants import Hat

class DPad(QWidget):
    """方向パッド（十字キー）ウィジェット"""
    directionChanged = Signal(Hat)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.current_direction: Hat = Hat.CENTER
        self.pressed: bool = False
    
    def paintEvent(self, event: QPaintEvent) -> None:
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
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.pressed = True
            self.updateDirection(event.position())
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pressed:
            self.updateDirection(event.position())
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.pressed:
            self.pressed = False
            self.current_direction = Hat.CENTER
            self.update()
            self.directionChanged.emit(Hat.CENTER)
    
    def updateDirection(self, pos: QPointF) -> None:
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
