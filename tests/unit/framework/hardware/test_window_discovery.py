import pytest

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.window_discovery import (
    WindowInfo,
    _list_windows_win32,
    resolve_window,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


def windows() -> tuple[WindowInfo, ...]:
    return (
        WindowInfo("Viewer", "hwnd-1", CaptureRect(0, 0, 640, 480)),
        WindowInfo("Viewer Settings", "hwnd-2", CaptureRect(0, 0, 320, 240)),
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


class FakeUser32:
    def EnumWindows(self, callback, lparam):
        callback(100, lparam)
        return True

    def IsWindowVisible(self, hwnd):
        return True

    def IsIconic(self, hwnd):
        return False

    def GetWindowTextLengthW(self, hwnd):
        return len("Viewer")

    def GetWindowTextW(self, hwnd, buffer, length):
        buffer.value = "Viewer"
        return len(buffer.value)

    def GetWindowRect(self, hwnd, rect):
        rect = rect._obj
        rect.left = 100
        rect.top = 200
        rect.right = 1400
        rect.bottom = 960
        return True

    def GetClientRect(self, hwnd, rect):
        rect = rect._obj
        rect.left = 0
        rect.top = 0
        rect.right = 1280
        rect.bottom = 720
        return True

    def ClientToScreen(self, hwnd, point):
        point = point._obj
        point.x = 110
        point.y = 230
        return True


def test_windows_list_uses_client_rect_in_screen_coordinates(monkeypatch) -> None:
    monkeypatch.setattr(
        "nyxpy.framework.core.hardware.window_discovery.ensure_capture_coordinate_space",
        lambda: None,
    )

    detected = _list_windows_win32(FakeUser32())

    assert detected == (
        WindowInfo(
            title="Viewer",
            identifier="100",
            rect=CaptureRect(left=110, top=230, width=1280, height=720),
            window_rect=CaptureRect(left=100, top=200, width=1300, height=760),
        ),
    )
