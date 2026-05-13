import threading
import time
from abc import ABC, abstractmethod
from typing import override

import cv2
import numpy as np

from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort


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


class CameraCaptureDevice(CaptureDeviceInterface):
    """
    キャプチャデバイスの非同期スレッド実装。
    内部で専用のスレッドを起動し、連続的にフレームを取得して最新フレームをキャッシュします。
    """

    def __init__(
        self,
        device_index: int = 0,
        api_pref: int = 0,
        fps: float = 60.0,
        logger: LoggerPort | None = None,
    ) -> None:
        self.logger = logger or NullLoggerPort()
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
                f"CameraCaptureDevice: Device {self.device_index} could not be opened."
            )
        # Try to set FPS and buffer size if supported
        try:
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        except Exception:
            self.logger.technical(
                "ERROR",
                "Failed to set FPS.",
                component="CameraCaptureDevice",
                event="capture.configure_failed",
            )
        try:
            # set the frame width and height to 1920x1080
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            if not (
                self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) == 1920
                and self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == 1080
            ):
                self.logger.technical(
                    "WARNING",
                    "Failed to set frame size to 1920x1080. Device may not support this resolution.",
                    component="CameraCaptureDevice",
                    event="capture.configure_failed",
                )
                # Try setting to a lower resolution
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 720)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        except Exception:
            self.logger.technical(
                "ERROR",
                "Failed to set frame size.",
                component="CameraCaptureDevice",
                event="capture.configure_failed",
            )
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            self.logger.technical(
                "ERROR",
                "Failed to set buffer size.",
                component="CameraCaptureDevice",
                event="capture.configure_failed",
            )
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        while self._running:
            begin = time.perf_counter()
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self.latest_frame = frame
            elapsed = time.perf_counter() - begin
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)  # Wait for the next frame

    def get_frame(self) -> cv2.typing.MatLike:
        """
        キャッシュされた最新のフレームを取得します。
        """
        with self._lock:
            if self.latest_frame is None:
                raise RuntimeError("CameraCaptureDevice: No frame available yet.")
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
