import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class AnalogStick(QWidget):
    """アナログスティックウィジェット"""

    valueChanged = Signal(float, float)  # 角度と強さのシグナル

    def __init__(self, parent: QWidget | None = None, is_left: bool = True) -> None:
        super().__init__(parent)
        self.is_left = is_left
        self._diameter = 60
        self.position = self._center()
        self.dragging = False
        self.setMouseTracking(True)

        # スティックの色
        self.stick_color = QColor(0, 120, 215) if is_left else QColor(215, 0, 0)
        self.set_diameter(self._diameter)

    def set_diameter(self, diameter: int) -> None:
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.position = self._center()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        diameter = min(self.width(), self.height())
        inset = diameter * 5 / 60
        base_rect = QRectF(inset, inset, diameter - inset * 2, diameter - inset * 2)
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        painter.drawEllipse(base_rect)

        stick_radius = diameter * 10 / 60
        stick_rect = QRectF(
            self.position.x() - stick_radius,
            self.position.y() - stick_radius,
            stick_radius * 2,
            stick_radius * 2,
        )
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.setBrush(QBrush(self.stick_color))
        painter.drawEllipse(stick_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.updateStickPosition(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.dragging:
            self.updateStickPosition(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self.position = self._center()
            self.update()
            self.valueChanged.emit(0.0, 0.0)  # 角度0、強さ0を送信

    def updateStickPosition(self, pos: QPointF) -> None:
        center = self._center()
        vector = QPointF(pos.x() - center.x(), pos.y() - center.y())

        distance = math.sqrt(vector.x() * vector.x() + vector.y() * vector.y())
        max_distance = self._max_distance()

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
            self.valueChanged.emit(0.0, 0.0)

        self.update()

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _max_distance(self) -> float:
        return min(self.width(), self.height()) / 3
