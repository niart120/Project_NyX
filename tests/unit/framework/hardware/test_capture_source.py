import pytest

from nyxpy.framework.core.hardware.capture_source import (
    CameraCaptureSourceConfig,
    CaptureRect,
    CaptureSourceKey,
    PonkanCaptureSourceConfig,
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


def test_capture_source_from_settings_creates_ponkan_capture_source() -> None:
    source = capture_source_from_settings(
        {
            "capture_source_type": "capture",
            "capture_provider": "ponkan",
            "capture_device_profile": "n3dsxl",
            "ponkan_backend": "d3xx-native",
            "ponkan_raw_slots": 3,
            "ponkan_output_queue_size": 4,
            "ponkan_drop_policy": "block",
            "ponkan_poll_interval": 0.01,
            "ponkan_read_timeout": None,
            "ponkan_collect_timing": True,
        }
    )

    assert isinstance(source, PonkanCaptureSourceConfig)
    assert source.device_profile == "n3dsxl"
    assert source.ponkan_backend == "d3xx-native"
    assert source.raw_slots == 3
    assert source.output_queue_size == 4
    assert source.drop_policy == "block"
    assert source.poll_interval == 0.01
    assert source.read_timeout is None
    assert source.collect_timing is True
    assert source.transform.aspect_box_enabled is True


def test_capture_source_rejects_invalid_ponkan_backend() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        capture_source_from_settings(
            {
                "capture_source_type": "capture",
                "ponkan_backend": "libusb",
            }
        )

    assert exc_info.value.code == "NYX_PONKAN_CAPTURE_BACKEND_INVALID"


def test_capture_source_key_includes_ponkan_runtime_settings() -> None:
    first = CaptureSourceKey.from_source(
        capture_source_from_settings(
            {
                "capture_source_type": "capture",
                "ponkan_backend": "auto",
            }
        )
    )
    second = CaptureSourceKey.from_source(
        capture_source_from_settings(
            {
                "capture_source_type": "capture",
                "ponkan_backend": "d3xx",
            }
        )
    )

    assert first != second


def test_capture_source_defers_ponkan_profile_validation_to_upstream_registry() -> None:
    source = capture_source_from_settings(
        {
            "capture_source_type": "capture",
            "capture_device_profile": "future_profile",
        }
    )

    assert isinstance(source, PonkanCaptureSourceConfig)
    assert source.device_profile == "future_profile"
    assert source.transform.aspect_box_enabled is False
