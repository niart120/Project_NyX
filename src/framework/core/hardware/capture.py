import cv2

class CaptureDevice:
    """
    キャプチャボードを抽象化するクラス。
    OpenCVなどを利用してデバイスから映像フレームを取得する。
    """
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.cap = None

    def initialize(self) -> None:
        self.cap = cv2.VideoCapture(self.device_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"CaptureDevice: Device {self.device_index} could not be opened.")

    def get_frame(self):
        if self.cap is None:
            raise RuntimeError("CaptureDevice: Device not initialized.")
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("CaptureDevice: Failed to capture frame.")
        return frame

    def release(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None


class CaptureManager:
    """
    複数のキャプチャデバイスを管理し、利用するデバイスを切り替える仕組みを提供。
    """
    def __init__(self):
        self.devices = {}
        self.active_device = None

    def register_device(self, name: str, device: CaptureDevice) -> None:
        self.devices[name] = device

    def set_active(self, name: str) -> None:
        if name not in self.devices:
            raise ValueError(f"CaptureManager: Device '{name}' not registered.")
        self.active_device = self.devices[name]
        self.active_device.initialize()

    def get_frame(self):
        if self.active_device is None:
            raise RuntimeError("CaptureManager: No active capture device.")
        return self.active_device.get_frame()

    def release_active(self) -> None:
        if self.active_device:
            self.active_device.release()
            self.active_device = None
