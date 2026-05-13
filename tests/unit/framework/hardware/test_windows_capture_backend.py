import numpy as np
import pytest

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.window_discovery import WindowInfo, WindowLocatorBackend
from nyxpy.framework.core.hardware.windows_capture_backend import WindowsGraphicsCaptureBackend
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class Locator(WindowLocatorBackend):
    def list_windows(self):
        return (WindowInfo("Viewer", "100", CaptureRect(0, 0, 2, 2)),)


class Control:
    def __init__(self) -> None:
        self.stopped = False
        self.waited = False

    def stop(self) -> None:
        self.stopped = True

    def wait(self) -> None:
        self.waited = True


class FakeFrame:
    def __init__(self, frame_buffer) -> None:
        self.frame_buffer = frame_buffer


class FakeWindowsCapture:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.frame_handler = None
        self.closed_handler = None
        self.control = Control()
        FakeWindowsCapture.instances.append(self)

    def event(self, handler):
        if handler.__name__ == "on_frame_arrived":
            self.frame_handler = handler
        elif handler.__name__ == "on_closed":
            self.closed_handler = handler
        return handler

    def start_free_threaded(self):
        bgra = np.array([[[1, 2, 3, 255]]], dtype=np.uint8)
        self.frame_handler(FakeFrame(bgra), self.control)
        return self.control


def capture_class_factory():
    return FakeWindowsCapture


def test_windows_backend_rejects_non_windows() -> None:
    backend = WindowsGraphicsCaptureBackend(
        capture_class_factory=capture_class_factory,
        platform_name="Linux",
    )
    session = backend.create_session(WindowCaptureSourceConfig(title_pattern="Viewer"), Locator())

    with pytest.raises(ConfigurationError, match="supported only on Windows"):
        session.start()


def test_windows_backend_import_error_message() -> None:
    def fail_import():
        raise ConfigurationError(
            "windows-capture optional dependency is required",
            code="NYX_CAPTURE_WINDOWS_CAPTURE_NOT_INSTALLED",
            component="test",
        )

    backend = WindowsGraphicsCaptureBackend(
        capture_class_factory=fail_import,
        platform_name="Windows",
        windows_build=18362,
    )
    session = backend.create_session(WindowCaptureSourceConfig(title_pattern="Viewer"), Locator())

    with pytest.raises(ConfigurationError, match="windows-capture optional dependency"):
        session.start()


def test_windows_session_updates_latest_frame_from_callback() -> None:
    FakeWindowsCapture.instances.clear()
    backend = WindowsGraphicsCaptureBackend(
        capture_class_factory=capture_class_factory,
        platform_name="Windows",
        windows_build=18362,
    )
    session = backend.create_session(
        WindowCaptureSourceConfig(title_pattern="Viewer", identifier="100"),
        Locator(),
    )

    session.start()
    try:
        frame = session.latest_frame()
    finally:
        session.stop()

    assert frame.shape == (1, 1, 3)
    assert frame[0, 0].tolist() == [1, 2, 3]
    assert FakeWindowsCapture.instances[0].kwargs["window_hwnd"] == 100
    assert session._capture is None
    assert FakeWindowsCapture.instances[0].control.stopped is True
    assert FakeWindowsCapture.instances[0].control.waited is True


class FakeWindowFrameWindowsCapture(FakeWindowsCapture):
    def start_free_threaded(self):
        bgra = np.arange(4 * 4 * 4, dtype=np.uint8).reshape((4, 4, 4))
        self.frame_handler(FakeFrame(bgra), self.control)
        return self.control


class WindowFrameLocator(WindowLocatorBackend):
    def list_windows(self):
        return (
            WindowInfo(
                "Viewer",
                "100",
                CaptureRect(1, 1, 2, 2),
                window_rect=CaptureRect(0, 0, 4, 4),
            ),
        )


def window_frame_capture_class_factory():
    return FakeWindowFrameWindowsCapture


def test_windows_session_crops_window_frame_to_client_rect() -> None:
    FakeWindowsCapture.instances.clear()
    backend = WindowsGraphicsCaptureBackend(
        capture_class_factory=window_frame_capture_class_factory,
        platform_name="Windows",
        windows_build=18362,
    )
    session = backend.create_session(
        WindowCaptureSourceConfig(title_pattern="Viewer", identifier="100"),
        WindowFrameLocator(),
    )

    session.start()
    try:
        frame = session.latest_frame()
        assert session._capture is FakeWindowsCapture.instances[0]
    finally:
        session.stop()

    raw = np.arange(4 * 4 * 4, dtype=np.uint8).reshape((4, 4, 4))
    assert frame.shape == (2, 2, 3)
    assert frame.tolist() == raw[1:3, 1:3, :3].tolist()


def test_windows_session_stop_is_idempotent() -> None:
    backend = WindowsGraphicsCaptureBackend(
        capture_class_factory=capture_class_factory,
        platform_name="Windows",
        windows_build=18362,
    )
    session = backend.create_session(WindowCaptureSourceConfig(title_pattern="Viewer"), Locator())

    session.start()
    session.stop()
    session.stop()
