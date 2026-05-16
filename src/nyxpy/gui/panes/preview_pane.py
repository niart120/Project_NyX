from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget

from nyxpy.framework.core.constants import (
    ScreenPoint,
    ScreenSize,
    TouchPoint,
    preview_point_to_3ds_touch,
    try_preview_point_to_hd_capture,
)
from nyxpy.framework.core.hardware.capture import CaptureDeviceInterface
from nyxpy.framework.core.io.adapters import CaptureFrameSourcePort
from nyxpy.framework.core.io.ports import FrameSourcePort
from nyxpy.framework.core.utils.helper import calc_aspect_size
from nyxpy.gui.widgets import AspectRatioLabel

SNAPSHOT_DIR = "snapshots"


class PreviewPane(QWidget):
    snapshot_taken = Signal(str)
    touch_down_requested = Signal(int, int)
    touch_move_requested = Signal(int, int)
    touch_up_requested = Signal()
    """
    Pane for showing camera preview and handling snapshots.
    """

    def __init__(
        self,
        capture_device: CaptureDeviceInterface | None = None,
        parent=None,
        preview_fps=30,
        frame_source: FrameSourcePort | None = None,
        fixed_preview_size: tuple[int, int] = (1280, 720),
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = AspectRatioLabel(16, 9)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMouseTracking(True)
        self.label.installEventFilter(self)
        self.setMouseTracking(True)
        self._fixed_preview_size = fixed_preview_size
        self._touch_active = False
        self._last_touch_point: TouchPoint | None = None
        self.label.setFixedSize(*fixed_preview_size)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)

        self.capture_device: CaptureDeviceInterface | None = capture_device
        self.frame_source: FrameSourcePort | None = frame_source
        if self.frame_source is None and capture_device is not None:
            self.frame_source = CaptureFrameSourcePort(capture_device)
        self.preview_fps = preview_fps  # プレビュー用のみ

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self.apply_fps()
        QTimer.singleShot(500, self.update_preview)

    def set_capture_device(self, device: CaptureDeviceInterface):
        self.capture_device = device
        self.frame_source = CaptureFrameSourcePort(device) if device is not None else None

    def set_frame_source(self, frame_source: FrameSourcePort | None) -> None:
        self.capture_device = None
        self.frame_source = frame_source

    def set_fixed_preview_size(self, width: int, height: int) -> None:
        self._fixed_preview_size = (width, height)
        self.label.setFixedSize(width, height)
        self.setFixedSize(width, height)

    def preview_widget_point_to_hd_capture_point(self, point: QPoint) -> ScreenPoint | None:
        return try_preview_point_to_hd_capture(
            ScreenPoint(point.x(), point.y()),
            preview_size=ScreenSize(self.label.width(), self.label.height()),
        )

    def _preview_widget_point_to_touch_point(self, point: QPoint) -> TouchPoint | None:
        try:
            return preview_point_to_3ds_touch(
                ScreenPoint(point.x(), point.y()),
                preview_size=ScreenSize(self.label.width(), self.label.height()),
            )
        except ValueError:
            return None

    def eventFilter(self, watched, event) -> bool:
        if watched is self.label and isinstance(event, QMouseEvent):
            match event.type():
                case QEvent.Type.MouseButtonPress:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._handle_touch_press(event.position().toPoint())
                        return True
                case QEvent.Type.MouseMove:
                    self._handle_touch_move(event.position().toPoint())
                    return self._touch_active
                case QEvent.Type.MouseButtonRelease:
                    if event.button() == Qt.MouseButton.LeftButton:
                        self._handle_touch_release()
                        return True
        return super().eventFilter(watched, event)

    def _handle_touch_press(self, point: QPoint) -> None:
        touch = self._preview_widget_point_to_touch_point(point)
        if touch is None:
            return
        self._touch_active = True
        self._last_touch_point = touch
        self.touch_down_requested.emit(touch.x, touch.y)

    def _handle_touch_move(self, point: QPoint) -> None:
        if not self._touch_active:
            return
        touch = self._preview_widget_point_to_touch_point(point)
        if touch is None or touch == self._last_touch_point:
            return
        self._last_touch_point = touch
        self.touch_move_requested.emit(touch.x, touch.y)

    def _handle_touch_release(self) -> None:
        if not self._touch_active:
            return
        self._touch_active = False
        self._last_touch_point = None
        self.touch_up_requested.emit()

    def pause(self) -> None:
        self.timer.stop()

    def resume(self) -> None:
        if self.isVisible() and self.frame_source is not None:
            self.apply_fps()

    def update_preview(self):
        if not self.isVisible() or self.frame_source is None:
            return
        frame = self.frame_source.try_latest_frame()
        if frame is None:
            return
        size = self.label.size()
        target_w, target_h = calc_aspect_size(size, self.label.aspect_w, self.label.aspect_h)
        target_w, target_h = (
            int(target_w * self.devicePixelRatio()),
            int(target_h * self.devicePixelRatio()),
        )

        frame = np.ascontiguousarray(frame)
        interpolation = (
            cv2.INTER_AREA
            if target_w <= frame.shape[1] and target_h <= frame.shape[0]
            else cv2.INTER_LINEAR
        )
        resized = cv2.resize(frame, (target_w, target_h), interpolation=interpolation)
        image = QImage(resized.data, target_w, target_h, target_w * 3, QImage.Format_BGR888)
        pix = QPixmap.fromImage(image)
        pix.setDevicePixelRatio(self.devicePixelRatio())
        self.label.setPixmap(pix)

    def take_snapshot(self):
        snaps_dir = Path.cwd() / SNAPSHOT_DIR
        snaps_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = snaps_dir / f"{timestamp}.png"
        if self.frame_source is None:
            msg = "プレビューがありません。スナップショットに失敗しました。"
        else:
            pix = self.frame_source.try_latest_frame()
            if pix is not None:
                target_w, target_h = 1280, 720
                pix = cv2.resize(pix, (target_w, target_h), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(filepath), pix)
                msg = f"スナップショット保存: {filepath.name}"
            else:
                msg = "プレビューがありません。スナップショットに失敗しました。"
        self.snapshot_taken.emit(msg)
        return msg

    def apply_fps(self):
        interval = int(1000 / self.preview_fps) if self.preview_fps > 0 else 1000
        self.timer.start(interval)

    def showEvent(self, event):
        super().showEvent(event)
        self.apply_fps()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()
