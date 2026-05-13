import os
import time

import pytest

from nyxpy.framework.core.hardware.capture_source import WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.window_capture import WindowCaptureDevice
from nyxpy.framework.core.hardware.window_discovery import DefaultWindowLocatorBackend
from nyxpy.framework.core.hardware.windows_capture_backend import WindowsGraphicsCaptureBackend


@pytest.mark.realdevice
def test_windows_capture_occluded_window_realdevice() -> None:
    title = os.environ.get("NYX_REAL_WINDOW_CAPTURE_TITLE")
    if not title:
        pytest.skip("NYX_REAL_WINDOW_CAPTURE_TITLE is not set")
    locator = DefaultWindowLocatorBackend()
    config = WindowCaptureSourceConfig(
        title_pattern=title,
        match_mode="contains",
        backend="windows_graphics_capture",
        fps=60.0,
    )
    device = WindowCaptureDevice(
        config,
        locator=locator,
        backend=WindowsGraphicsCaptureBackend(),
    )

    try:
        device.initialize()
    except Exception as exc:
        pytest.skip(f"Windows Graphics Capture backend is not available: {exc}")
    try:
        time.sleep(1.0)
        frame = device.get_frame()
    finally:
        device.release()

    assert frame.ndim == 3
    assert frame.shape[2] == 3
