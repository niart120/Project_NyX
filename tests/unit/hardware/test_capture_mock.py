import time
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture import (
    AsyncCaptureDevice,
    DummyCaptureDevice,
)


# ダミーの VideoCapture クラス
class DummyVideoCapture:
    def __init__(self, device_index, *args, **kwargs):
        self.device_index = device_index
        self._is_opened = True
        self.read_count = 0

    def isOpened(self):
        return self._is_opened

    def read(self) -> tuple[bool, cv2.typing.MatLike]:
        # 最初の1回目のみ有効なフレームを返す(黒画面)
        self.read_count += 1
        if self.read_count == 1:
            return True, np.zeros((720, 1280, 3), dtype=np.uint8)
        # 2回目以降は常に成功しても同じ値を返す
        return True, np.zeros((720, 1280, 3), dtype=np.uint8)

    def release(self):
        self._is_opened = False


# テストケース１: AsyncCaptureDevice の正常な初期化、フレーム取得、クローズ
def test_async_capture_device_initialize_and_get_frame():
    with patch("nyxpy.framework.core.hardware.capture.cv2.VideoCapture", new=DummyVideoCapture):
        device = AsyncCaptureDevice(device_index=5, fps=100.0)
        device.initialize()

        # 最初のフレームが取得できていることを確認
        time.sleep(0.05)
        frame1 = device.get_frame()
        assert isinstance(frame1, np.ndarray)
        assert frame1.shape == (720, 1280, 3)

        # 内部のread_countをリセットして動作確認
        device.cap.read_count = 0
        time.sleep(0.05)
        frame2 = device.get_frame()
        assert isinstance(frame2, np.ndarray)
        assert frame2.shape == (720, 1280, 3)

        device.release()
        assert device.cap is None


# テストケース２: 初期化時にデバイスがオープンできない場合の異常系テスト
class DummyVideoCaptureNotOpened:
    def __init__(self, *args, **kwargs):
        pass

    def isOpened(self):
        return False

    def read(self):
        return False, None

    def release(self):
        pass


def test_async_capture_device_initialize_failure():
    with patch(
        "nyxpy.framework.core.hardware.capture.cv2.VideoCapture",
        new=DummyVideoCaptureNotOpened,
    ):
        device = AsyncCaptureDevice(device_index=1)
        with pytest.raises(RuntimeError, match="AsyncCaptureDevice: Device 1 could not be opened."):
            device.initialize()


# テストケース３: get_latest_frame がフレーム未更新の場合の動作確認
def test_get_latest_frame_no_update():
    with patch("nyxpy.framework.core.hardware.capture.cv2.VideoCapture", new=DummyVideoCapture):
        device = AsyncCaptureDevice(device_index=2, fps=20.0)
        device.initialize()
        # 強制的に latest_frame を None
        device.latest_frame = None
        with pytest.raises(RuntimeError, match="AsyncCaptureDevice: No frame available yet."):
            device.get_frame()
        device.release()


def test_dummy_capture_device_returns_black_frame():
    device = DummyCaptureDevice()
    assert isinstance(device, DummyCaptureDevice)

    frame = device.get_frame()
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (720, 1280, 3)
