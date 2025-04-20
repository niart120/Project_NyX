from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, Signal, QTimer
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from nyxpy.framework.core.utils.helper import calc_aspect_size
from nyxpy.gui.widgets import AspectRatioLabel

SNAPSHOT_DIR = "snapshots"

class PreviewPane(QWidget):
    snapshot_taken = Signal(str)
    """
    Pane for showing camera preview and handling snapshots.
    """
    def __init__(self, settings_service, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        # Preview label
        self.label = AspectRatioLabel(settings_service.global_settings.get("capture_aspect_w",16),
                                      settings_service.global_settings.get("capture_aspect_h",9))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumHeight(100)
        layout.addWidget(self.label)
        # Capture device init and timer
        self.capture_manager = settings_service.capture_manager
        self.settings = settings_service.global_settings
        self.capture_manager.auto_register_devices()
        # set default or first device
        devices = self.capture_manager.list_devices()
        default_cap = self.settings.get("capture_device", "")
        try:
            if default_cap and default_cap in devices:
                self.capture_manager.set_active(default_cap)
            elif devices:
                self.capture_manager.set_active(devices[0])
        except Exception:
            pass
        # use QTimer to periodically update preview
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        # Start timer immediately to ensure preview updates even if showEvent isn't called
        self.apply_fps()
        # Initial frame render
        self.update_preview()

    def update_preview(self):
        try:
            frame = self.capture_manager.get_active_device().get_frame()
            if frame is None:
                return
                
            # Calculate target size based on label aspect ratio
            size = self.label.size()
            target_w, target_h = calc_aspect_size(size, self.label.aspect_w, self.label.aspect_h)
            
            # np.arrayの場合のみflagsにアクセス
            if hasattr(frame, 'flags') and hasattr(frame.flags, '__getitem__'):
                if not frame.flags.get('C_CONTIGUOUS', True):
                    frame = np.ascontiguousarray(frame)
            
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            image = QImage(resized.data, target_w, target_h, target_w*3, QImage.Format_BGR888)
            pix = QPixmap.fromImage(image)
            self.label.setPixmap(pix)
        except Exception:
            # エラー時は何もしない（既存の動作を維持）
            return

    def take_snapshot(self):
        # Capture current pixmap and save to file
        snaps_dir = Path.cwd() / SNAPSHOT_DIR
        snaps_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = snaps_dir / f"{timestamp}.png"
        pix = self.capture_manager.get_active_device().get_frame()
       
        # save to file        
        if pix is not None:
             # resize to 1280x720
            target_w, target_h = 1280, 720
            pix = cv2.resize(pix, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            
            # save image
            cv2.imwrite(str(filepath), pix)
            msg = f"スナップショット保存: {filepath.name}"
        else:
            msg = "プレビューがありません。スナップショットに失敗しました。"
        # Emit signal and return message
        self.snapshot_taken.emit(msg)
        return msg

    def set_active_device(self, device: str):
        """Change active capture device."""
        try:
            self.capture_manager.set_active(device)
        except Exception:
            pass

    def apply_fps(self):
        """Start or restart the preview update timer based on settings."""
        fps = self.settings.get("capture_fps", 30)
        interval = int(1000 / fps) if fps > 0 else 1000
        self.timer.start(interval)
        # Immediately trigger one update to reflect current size
        self.update_preview()

    def showEvent(self, event):
        super().showEvent(event)
        # Start timer when pane is shown
        self.apply_fps()
