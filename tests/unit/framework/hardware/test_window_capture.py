import time

import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import (
    CaptureRect,
    ScreenRegionCaptureSourceConfig,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.window_capture import (
    ScreenRegionCaptureDevice,
    WindowCaptureBackend,
    WindowCaptureDevice,
    WindowCaptureSession,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo, WindowLocatorBackend


class FakeSession(WindowCaptureSession):
    def __init__(self, frame=None, *, fail=False) -> None:
        self.frame = frame if frame is not None else np.zeros((2, 2, 3), dtype=np.uint8)
        self.fail = fail
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def latest_frame(self):
        if self.fail:
            raise RuntimeError("not ready")
        return self.frame

    def stop(self) -> None:
        self.stopped = True


class FakeBackend(WindowCaptureBackend):
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.released = False

    def create_session(self, config, locator):
        return self.session

    def release(self) -> None:
        self.released = True


class FakeLocator(WindowLocatorBackend):
    def list_windows(self):
        return (WindowInfo("Viewer", "1", CaptureRect(0, 0, 2, 2)),)


def test_screen_region_capture_device_returns_copy() -> None:
    frame = np.full((2, 2, 3), 7, dtype=np.uint8)
    session = FakeSession(frame)
    backend = FakeBackend(session)
    device = ScreenRegionCaptureDevice(
        ScreenRegionCaptureSourceConfig(CaptureRect(0, 0, 2, 2), fps=120.0),
        backend=backend,
    )

    device.initialize()
    try:
        captured = device.get_frame()
        captured[0, 0] = 255
    finally:
        device.release()

    assert np.all(frame == 7)
    assert session.started is True
    assert session.stopped is True
    assert backend.released is True


def test_window_capture_device_raises_before_first_frame() -> None:
    device = WindowCaptureDevice(
        WindowCaptureSourceConfig(title_pattern="Viewer", fps=120.0),
        locator=FakeLocator(),
        backend=FakeBackend(FakeSession(fail=True)),
    )

    device.initialize()
    try:
        with pytest.raises(RuntimeError):
            device.get_frame()
    finally:
        device.release()


def test_window_capture_device_release_is_idempotent() -> None:
    device = WindowCaptureDevice(
        WindowCaptureSourceConfig(title_pattern="Viewer", fps=120.0),
        locator=FakeLocator(),
        backend=FakeBackend(FakeSession()),
    )

    device.initialize()
    time.sleep(0.01)
    device.release()
    device.release()
