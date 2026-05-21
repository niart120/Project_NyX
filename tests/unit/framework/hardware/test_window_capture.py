import time

import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import (
    CaptureRect,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.window_capture import (
    AutoWindowCaptureBackend,
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


def test_auto_backend_fallback_occurs_inside_session_start() -> None:
    failed = FakeSession(fail=False)

    def fail_start() -> None:
        failed.started = True
        raise RuntimeError("wgc unavailable")

    failed.start = fail_start
    fallback = FakeSession(np.full((2, 2, 3), 9, dtype=np.uint8))
    backend = AutoWindowCaptureBackend(
        backend_factories=(
            ("windows_graphics_capture", lambda: FakeBackend(failed)),
            ("mss", lambda: FakeBackend(fallback)),
        ),
        platform_name="Windows",
    )

    session = backend.create_session(
        WindowCaptureSourceConfig(title_pattern="Viewer"), FakeLocator()
    )
    session.start()
    try:
        assert session.latest_frame()[0, 0].tolist() == [9, 9, 9]
    finally:
        session.stop()
        backend.release()

    assert failed.started is True
    assert fallback.started is True
    assert session.chosen_backend == "mss"


def test_explicit_backend_does_not_fallback() -> None:
    failed = FakeSession()

    def fail_start() -> None:
        raise RuntimeError("explicit failed")

    failed.start = fail_start
    backend = FakeBackend(failed)
    session = backend.create_session(
        WindowCaptureSourceConfig(title_pattern="Viewer"), FakeLocator()
    )

    with pytest.raises(RuntimeError, match="explicit failed"):
        session.start()
