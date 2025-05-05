from typing import override
import cv2
from cv2_enumerate_cameras import enumerate_cameras
from abc import ABC, abstractmethod
import threading
import time
import platform

import numpy as np

from nyxpy.framework.core.logger.log_manager import log_manager


class CaptureDeviceInterface(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """
        デバイスの初期化を行う
        """
        pass

    @abstractmethod
    def get_frame(self) -> cv2.typing.MatLike:
        """
        最新のフレームを取得する
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """
        デバイスの解放を行う
        """
        pass


class AsyncCaptureDevice:
    """
    キャプチャデバイスの非同期スレッド実装。
    内部で専用のスレッドを起動し、連続的にフレームを取得して最新フレームをキャッシュします。
    """

    def __init__(self, device_index: int = 0, api_pref: int = 0, fps: float = 60.0) -> None:
        self.device_index = device_index
        self.api_pref = api_pref  # API preference
        self.cap: cv2.VideoCapture = None
        self.latest_frame: cv2.typing.MatLike = None
        self._running = False
        self.fps = fps  # キャプチャのフレームレート
        self._interval = 1.0 / fps if fps > 0 else 1.0 / 60.0  # キャプチャ間隔（秒）
        self._lock = threading.Lock()
        self._thread = None

    def initialize(self) -> None:
        self.cap = cv2.VideoCapture(self.device_index, self.api_pref)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"AsyncCaptureDevice: Device {self.device_index} could not be opened."
            )
        # Try to set FPS and buffer size if supported
        try:
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        except Exception:
            log_manager.log("ERROR", "Failed to set FPS.", component="AsyncCaptureDevice")
        try:
            # set the frame width and height to 1920x1080
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        except Exception:
            log_manager.log("ERROR", "Failed to set frame size.", component="AsyncCaptureDevice")
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            log_manager.log("ERROR", "Failed to set buffer size.", component="AsyncCaptureDevice")
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self.latest_frame = frame
            time.sleep(self._interval)

    def get_frame(self) -> cv2.typing.MatLike:
        """
        キャッシュされた最新のフレームを取得します。
        """
        with self._lock:
            if self.latest_frame is None:
                raise RuntimeError("AsyncCaptureDevice: No frame available yet.")
            # Return a copy of the latest or the latest frame
            return self.latest_frame.copy()

    def release(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join()
        if self.cap:
            self.cap.release()
            self.cap = None


class DummyCaptureDevice(CaptureDeviceInterface):
    """
    キャプチャデバイスのダミー実装。
    実際のデバイスがない場合に使用される。
    何もせず、常に黒画面を返す。
    """

    def __init__(self):
        # DummyCaptureDevice の初期化を行う
        # 返却用の黒画面(1280x720)を生成
        self._frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    @override
    def initialize(self) -> None:
        """
        ダミーキャプチャデバイスの初期化を行う。
        """
        pass

    @override
    def get_frame(self) -> cv2.typing.MatLike:
        """
        ダミーキャプチャデバイスからフレームを取得する。
        """
        return self._frame

    @override
    def release(self) -> None:
        """
        ダミーキャプチャデバイスのリソースを解放する。
        """
        pass


class CaptureManager:
    """
    複数のキャプチャデバイスを管理し、利用するデバイスを切り替える仕組みを提供します。
    非同期キャプチャ版として AsyncCaptureDevice を利用します。
    """

    def __init__(self):
        self.devices = {}
        self.active_device: AsyncCaptureDevice = None
        self._default_device = ""
        # Add dummy device by default for faster startup
        self.register_device("ダミーデバイス", DummyCaptureDevice())

    def auto_register_devices(self) -> None:
        """
        キャプチャデバイスを自動検出して登録します。
        """
        # Start a background thread to detect devices to avoid blocking the UI
        thread = threading.Thread(target=self._detect_devices_thread, daemon=True)
        thread.start()

    def set_default_device(self, device_name: str) -> None:
        """
        デフォルトのデバイス設定を保存します。デバイス検出後に自動的に適用されます。
        """
        self._default_device = device_name

    def _detect_devices_thread(self) -> None:
        """
        バックグラウンドでデバイスを検出するスレッド処理。
        UIをブロックせずにデバイスを検出します。
        """
        # OS に応じてデバイスを登録
        # Windows, Linux では enumerate_cameras() を利用 / macOS では手動で登録する必要がある
        os_name = platform.system()
        try:
            match os_name:
                case "Windows":
                    self._detect_windows_devices()
                case "Linux":
                    self._detect_linux_devices()
                case "Darwin":
                    self._detect_macos_devices()
                case _:
                    # Just use dummy device for unsupported platforms
                    pass

            # デバイス検出が完了したら、デフォルト設定を適用
            if self._default_device and self._default_device in self.devices:
                self.set_active(self._default_device)
        # Ensure we always have at least the dummy device
        except Exception:
            import traceback

            traceback.print_exc()
            # Ensure we always have at least the dummy device
            if "ダミーデバイス" not in self.devices:
                self.register_device("ダミーデバイス", DummyCaptureDevice())

    def _detect_windows_devices(self):
        # Windows uses DirectShow
        for camera_info in enumerate_cameras(cv2.CAP_DSHOW):
            name = f"{camera_info.index}: {camera_info.name}"
            device = AsyncCaptureDevice(device_index=camera_info.index, api_pref=cv2.CAP_DSHOW, fps=60.0)
            self.register_device(name, device)

    def _detect_linux_devices(self):
        # Linux uses V4L2
        for camera_info in enumerate_cameras(cv2.CAP_V4L2):
            name = f"{camera_info.index}: {camera_info.name}"
            device = AsyncCaptureDevice(device_index=camera_info.index, api_pref=cv2.CAP_V4L2, fps=60.0)
            self.register_device(name, device)

    def _detect_macos_devices(self):
        # macOS: Optimize by checking only first 5 indices instead of 20
        log_level = cv2.getLogLevel()
        cv2.setLogLevel(0)  # ログレベルを無効化
        try:
            # Reduce the search range from 20 to 5
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    cap.release()
                    name = f"macOS Camera {i}"
                    device = AsyncCaptureDevice(device_index=i, fps=60.0)
                    self.register_device(name, device)
        finally:
            cv2.setLogLevel(log_level)

    def list_devices(self) -> list[str]:
        """
        登録されているキャプチャデバイスの名前一覧を返します。
        """
        return list(self.devices.keys())

    def register_device(self, name: str, device: CaptureDeviceInterface) -> None:
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

    def get_active_device(self):
        """
        現在アクティブなキャプチャデバイスを返します。
        実際のフレーム取得は、このデバイスのメソッド（例: get_frame()）に委ねます。
        もしアクティブなデバイスが存在しない場合は、RuntimeError を発生させます。
        """
        if self.active_device is None:
            # Use dummy device instead of raising an error
            self.set_active("ダミーデバイス")
        return self.active_device

    def release_active(self) -> None:
        if self.active_device:
            self.active_device.release()
            self.active_device = None
