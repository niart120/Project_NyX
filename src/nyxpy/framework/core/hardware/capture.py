import cv2
import threading
import time

class AsyncCaptureDevice:
    """
    キャプチャデバイスの非同期スレッド実装。
    内部で専用のスレッドを起動し、連続的にフレームを取得して最新フレームをキャッシュします。
    """
    def __init__(self, device_index: int = 0, interval: float = 1.0/30.0) -> None:
        self.device_index = device_index
        self.cap:cv2.VideoCapture = None
        self.latest_frame:cv2.typing.MatLike = None
        self._running = False
        self.interval = interval  # キャプチャ間隔（秒）
        self._lock = threading.Lock()
        self._thread = None

    def initialize(self) -> None:
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"AsyncCaptureDevice: Device {self.device_index} could not be opened.")
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self.latest_frame = frame
            time.sleep(self.interval)

    def get_latest_frame(self)->cv2.typing.MatLike:
        """
        キャッシュされた最新のフレームを取得します。
        """
        with self._lock:
            return self.latest_frame

    def release(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join()
        if self.cap:
            self.cap.release()
            self.cap = None

class CaptureManager:
    """
    複数のキャプチャデバイスを管理し、利用するデバイスを切り替える仕組みを提供します。
    非同期キャプチャ版として AsyncCaptureDevice を利用します。
    """
    def __init__(self):
        self.devices = {}
        self.active_device:AsyncCaptureDevice = None

    def register_device(self, name: str, device: AsyncCaptureDevice) -> None:
        self.devices[name] = device

    def set_active(self, name: str) -> None:
        if name not in self.devices:
            raise ValueError(f"CaptureManager: Device '{name}' not registered.")
        self.active_device = self.devices[name]
        self.active_device.initialize()

    def get_frame(self)->cv2.typing.MatLike:
        if self.active_device is None:
            raise RuntimeError("CaptureManager: No active capture device.")
        frame = self.active_device.get_latest_frame()
        if frame is None:
            raise RuntimeError("CaptureManager: No frame available yet.")
        return frame

    def release_active(self) -> None:
        if self.active_device:
            self.active_device.release()
            self.active_device = None