import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from nyxpy.framework.core.constants import Hat


class DPad(QWidget):
    """方向パッド（十字キー）ウィジェット"""

    directionChanged = Signal(Hat)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_diameter(70)
        self.current_direction: Hat = Hat.CENTER
        self.pressed: bool = False

    def set_diameter(self, diameter: int) -> None:
        self.setFixedSize(diameter, diameter)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        unit = min(self.width(), self.height()) / 70

        # 基本の十字形を描画
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.setBrush(QBrush(QColor(60, 60, 60)))

        painter.drawEllipse(QRectF(27 * unit, 27 * unit, 16 * unit, 16 * unit))

        up_path = QPainterPath()
        up_path.addRoundedRect(
            QRectF(27 * unit, 5 * unit, 16 * unit, 25 * unit),
            5 * unit,
            5 * unit,
        )

        right_path = QPainterPath()
        right_path.addRoundedRect(
            QRectF(40 * unit, 27 * unit, 25 * unit, 16 * unit),
            5 * unit,
            5 * unit,
        )

        down_path = QPainterPath()
        down_path.addRoundedRect(
            QRectF(27 * unit, 40 * unit, 16 * unit, 25 * unit),
            5 * unit,
            5 * unit,
        )

        left_path = QPainterPath()
        left_path.addRoundedRect(
            QRectF(5 * unit, 27 * unit, 25 * unit, 16 * unit),
            5 * unit,
            5 * unit,
        )

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
        center_x = self.width() / 2
        center_y = self.height() / 2
        x, y = pos.x() - center_x, pos.y() - center_y

        dead_zone = min(self.width(), self.height()) * 8 / 70
        if abs(x) < dead_zone and abs(y) < dead_zone:
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
