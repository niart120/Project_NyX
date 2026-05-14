import ctypes
import os

import pytest

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.window_discovery import (
    DefaultWindowLocatorBackend,
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


def test_windows_list_works_without_windows_callback_type(monkeypatch) -> None:
    monkeypatch.delattr(ctypes, "WINFUNCTYPE", raising=False)
    monkeypatch.setattr(
        "nyxpy.framework.core.hardware.window_discovery.ensure_capture_coordinate_space",
        lambda: None,
    )

    detected = _list_windows_win32(FakeUser32())

    assert detected[0].identifier == "100"


def test_default_windows_resolve_uses_identifier_without_enumerating(monkeypatch) -> None:
    expected = WindowInfo("Viewer", "100", CaptureRect(10, 20, 640, 480))
    monkeypatch.setattr("nyxpy.framework.core.hardware.window_discovery.platform.system", lambda: "Windows")
    monkeypatch.setattr(
        "nyxpy.framework.core.hardware.window_discovery._window_info_from_hwnd",
        lambda hwnd: expected if hwnd == 100 else None,
    )
    monkeypatch.setattr(
        DefaultWindowLocatorBackend,
        "list_windows",
        lambda self: (_ for _ in ()).throw(AssertionError("list_windows must not be called")),
    )

    resolved = DefaultWindowLocatorBackend().resolve(
        WindowCaptureSourceConfig(title_pattern="Missing", identifier="100")
    )

    assert resolved is expected


class OwnProcessUser32(FakeUser32):
    def GetWindowThreadProcessId(self, hwnd, process_id):
        process_id._obj.value = os.getpid()
        return 1

    def GetWindowTextLengthW(self, hwnd):
        raise AssertionError("own process window text must not be queried from worker thread")


def test_windows_list_skips_own_process_windows_before_reading_title(monkeypatch) -> None:
    monkeypatch.setattr(
        "nyxpy.framework.core.hardware.window_discovery.ensure_capture_coordinate_space",
        lambda: None,
    )

    assert _list_windows_win32(OwnProcessUser32()) == ()
