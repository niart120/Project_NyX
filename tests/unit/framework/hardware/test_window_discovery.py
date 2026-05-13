import pytest

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.window_discovery import (
    WindowDiscoveryDiagnostics,
    WindowInfo,
    resolve_window,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def windows() -> tuple[WindowInfo, ...]:
    return (
        WindowInfo("Viewer", "hwnd-1", CaptureRect(0, 0, 640, 480), process_id=10),
        WindowInfo("Viewer Settings", "hwnd-2", CaptureRect(0, 0, 320, 240), process_id=11),
    )


def test_window_title_exact_match() -> None:
    resolved = resolve_window(
        windows(),
        WindowCaptureSourceConfig(title_pattern="Viewer", match_mode="exact"),
    )

    assert resolved.identifier == "hwnd-1"


def test_window_title_contains_match_rejects_ambiguous_candidates() -> None:
    with pytest.raises(ConfigurationError, match="ambiguous"):
        resolve_window(
            windows(),
            WindowCaptureSourceConfig(title_pattern="Viewer", match_mode="contains"),
        )


def test_window_identifier_takes_priority() -> None:
    resolved = resolve_window(
        windows(),
        WindowCaptureSourceConfig(title_pattern="Missing", identifier="hwnd-2"),
    )

    assert resolved.title == "Viewer Settings"


def test_window_discovery_diagnostics_summary() -> None:
    diagnostics = WindowDiscoveryDiagnostics(
        platform_name="Windows",
        total_handles=10,
        visible_handles=4,
        titled_handles=3,
        valid_rect_handles=2,
        returned_windows=2,
    )

    assert diagnostics.summary() == "platform=Windows total=10 visible=4 titled=3 rect=2 returned=2"
