import cv2
from cv2_enumerate_cameras import enumerate_cameras
import threading
import time
import platform

from nyxpy.framework.core import api

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
    
    def auto_register_devices(self) -> None:
        """
        キャプチャデバイスを自動検出して登録します。
        """
        # アクティブなデバイスをリリース
        self.release_active()
        # OS に応じてデバイスを登録
        # Windows, Linux では enumerate_cameras() を利用 / macOS では手動で登録する必要がある
        os_name = platform.system()
        match os_name:
            case "Windows":
                for camera_info in enumerate_cameras(apiPreference=cv2.CAP_DSHOW): #windowsの場合のバックエンドはDirectShow
                    name = f'{camera_info.index}: {camera_info.name}'
                    device = AsyncCaptureDevice(device_index=camera_info.index)
                    self.register_device(name, device)
            case "Linux":
                for camera_info in enumerate_cameras(cv2.CAP_V4L2): #Linuxの場合のバックエンドはV4L2
                    name = f'{camera_info.index}: {camera_info.name}'
                    device = AsyncCaptureDevice(device_index=camera_info.index)
                    self.register_device(name, device)
            case "Darwin":
                # macOS の場合の処理を追加することも可能
                # HACK: macOS の場合は enumerate_cameras() が動作しないため、手動で登録する必要がある
                # デバイス番号を0から20までの範囲で決め打ちで登録する
                log_level = cv2.getLogLevel()
                cv2.setLogLevel(0)  # ログレベルを無効化
                # 0から20までのカメラを登録する（実際には存在しない場合もある）
                for i in range(20):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        cap.release()
                        name = f"macOS Camera {i}"
                        device = AsyncCaptureDevice(device_index=i)
                        self.register_device(name, device)
                
                cv2.setLogLevel(log_level)
        
            case _:
                raise RuntimeError(f"Unsupported OS: {os_name}.")
            
    def list_devices(self) -> list[str]:
        """
        登録されているキャプチャデバイスの名前一覧を返します。
        """
        return list(self.devices.keys())

    def register_device(self, name: str, device: AsyncCaptureDevice) -> None:
        self.devices[name] = device

    def set_active(self, name: str) -> None:
        """
        指定されたデバイスをアクティブにします。
        """
        # アクティブなデバイスをリリース
        self.release_active()

        # デバイスが登録されているか確認
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