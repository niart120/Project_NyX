import pytest

from nyxpy.framework.core.hardware.capture_source import (
    CameraCaptureSourceConfig,
    CaptureRect,
    CaptureSourceKey,
    WindowCaptureSourceConfig,
    capture_source_from_settings,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def test_capture_rect_to_mss_monitor() -> None:
    rect = CaptureRect(left=10, top=20, width=300, height=200)

    assert rect.to_mss_monitor() == {"left": 10, "top": 20, "width": 300, "height": 200}


def test_capture_source_from_settings_uses_source_default_fps() -> None:
    window_source = capture_source_from_settings(
        {
            "capture_source_type": "window",
            "capture_window_title": "Viewer",
        }
    )

    assert isinstance(window_source, WindowCaptureSourceConfig)
    assert window_source.fps == 30.0


def test_capture_source_from_settings_rejects_removed_screen_region_source() -> None:
    with pytest.raises(ConfigurationError, match="invalid capture source type"):
        capture_source_from_settings(
            {
                "capture_source_type": "screen_region",
            }
        )


def test_capture_source_key_includes_transform() -> None:
    raw = CaptureSourceKey.from_source(CameraCaptureSourceConfig(device_name="Camera1"))
    boxed = CaptureSourceKey.from_source(
        capture_source_from_settings(
            {
                "capture_source_type": "camera",
                "capture_device": "Camera1",
                "capture_aspect_box_enabled": True,
            }
        )
    )

    assert raw != boxed
