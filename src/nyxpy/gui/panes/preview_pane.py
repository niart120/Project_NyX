from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, Signal, QTimer
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from nyxpy.framework.core.utils.helper import calc_aspect_size
from nyxpy.gui.events import EventBus, EventType
from nyxpy.gui.widgets import AspectRatioLabel

SNAPSHOT_DIR = "snapshots"


class PreviewPane(QWidget):
    snapshot_taken = Signal(str)
    """
    Pane for showing camera preview and handling snapshots.
    """

    def __init__(self, capture_device=None, parent=None, preview_fps=30):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.label = AspectRatioLabel(16, 9)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumHeight(100)
        layout.addWidget(self.label)

        self.capture_device = capture_device
        self.preview_fps = preview_fps      # プレビュー用のみ
        self.event_bus = EventBus.get_instance()
        self.event_bus.subscribe(EventType.CAPTURE_DEVICE_CHANGED, self.on_capture_device_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self.apply_fps()
        QTimer.singleShot(500, self.update_preview)

    def on_capture_device_changed(self, data):
        self.set_capture_device(data['device'])

    def set_capture_device(self, device):
        self.capture_device = device
        self.update_preview()

    def update_preview(self):
        if not self.isVisible() or self.capture_device is None:
            return
        try:
            frame = self.capture_device.get_frame()
            if frame is None:
                return
        except RuntimeError:
            return
        size = self.label.size()
        target_w, target_h = calc_aspect_size(
            size, self.label.aspect_w, self.label.aspect_h
        )
        if hasattr(frame, "flags") and hasattr(frame.flags, "__getitem__"):
            if not frame.flags["C_CONTIGUOUS"]:
                frame = np.ascontiguousarray(frame)
        resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
        image = QImage(
            resized.data, target_w, target_h, target_w * 3, QImage.Format_BGR888
        )
        pix = QPixmap.fromImage(image)
        self.label.setPixmap(pix)

    def take_snapshot(self):
        snaps_dir = Path.cwd() / SNAPSHOT_DIR
        snaps_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = snaps_dir / f"{timestamp}.png"
        if self.capture_device is None:
            msg = "プレビューがありません。スナップショットに失敗しました。"
        else:
            pix = self.capture_device.get_frame()
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
