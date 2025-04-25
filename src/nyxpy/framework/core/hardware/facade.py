from nyxpy.framework.core.hardware.serial_comm import SerialManager
from nyxpy.framework.core.hardware.capture import CaptureManager


class HardwareFacade:
    """
    ハードウェア操作のためのシンプルなインターフェースを提供するファサードクラスで、
    アクティブなシリアルデバイスとキャプチャデバイスのドライバに処理を委譲します。

    properties:
        serial_manager (SerialManager): シリアルデバイス通信を処理するマネージャ。
        capture_manager (CaptureManager): キャプチャデバイス操作を処理するマネージャ。
    """

    def __init__(self, serial_manager: SerialManager, capture_manager: CaptureManager):
        self.serial_manager = serial_manager
        self.capture_manager = capture_manager

    def send(self, data: bytes) -> None:
        # アクティブなシリアルデバイスのドライバへ委譲
        active_device = self.serial_manager.get_active_device()
        active_device.send(data)

    def capture(self):
        # アクティブなキャプチャデバイスのドライバへ委譲
        active_device = self.capture_manager.get_active_device()
        return active_device.get_frame()
