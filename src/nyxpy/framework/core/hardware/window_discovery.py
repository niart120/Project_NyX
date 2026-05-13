from __future__ import annotations

import ctypes
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.platform_capture import ensure_capture_coordinate_space
from nyxpy.framework.core.macro.exceptions import ConfigurationError


@dataclass(frozen=True)
class WindowInfo:
    title: str
    identifier: str | int
    rect: CaptureRect
    window_rect: CaptureRect | None = None
    app_name: str | None = None

    @property
    def display_name(self) -> str:
        return self.title


class WindowLocatorBackend(ABC):
    @abstractmethod
    def list_windows(self) -> tuple[WindowInfo, ...]:
        pass

    def resolve(self, config: WindowCaptureSourceConfig) -> WindowInfo:
        return resolve_window(self.list_windows(), config)


class DefaultWindowLocatorBackend(WindowLocatorBackend):
    def list_windows(self) -> tuple[WindowInfo, ...]:
        if platform.system() != "Windows":
            return ()
        return _list_windows_win32()


def resolve_window(
    windows: tuple[WindowInfo, ...],
    config: WindowCaptureSourceConfig,
) -> WindowInfo:
    if config.identifier not in (None, ""):
        identifier = str(config.identifier)
        for window in windows:
            if str(window.identifier) == identifier:
                return window

    pattern = config.title_pattern.strip()
    if not pattern:
        raise ConfigurationError(
            "capture window title is not selected",
            code="NYX_CAPTURE_WINDOW_NOT_SELECTED",
            component="WindowLocatorBackend",
        )

    if config.match_mode == "exact":
        matches = [window for window in windows if window.title == pattern]
    elif config.match_mode == "contains":
        matches = [window for window in windows if pattern in window.title]
    else:
        raise ConfigurationError(
            "invalid capture window match mode",
            code="NYX_CAPTURE_WINDOW_MATCH_MODE_INVALID",
            component="WindowLocatorBackend",
            details={"match_mode": config.match_mode},
        )
    if not matches:
        raise ConfigurationError(
            "capture window not found",
            code="NYX_CAPTURE_WINDOW_NOT_FOUND",
            component="WindowLocatorBackend",
            details={"title_pattern": pattern, "match_mode": config.match_mode},
        )
    if len(matches) > 1:
        raise ConfigurationError(
            "capture window match is ambiguous",
            code="NYX_CAPTURE_WINDOW_AMBIGUOUS",
            component="WindowLocatorBackend",
            details={
                "title_pattern": pattern,
                "match_mode": config.match_mode,
                "matches": [window.title for window in matches],
            },
        )
    return matches[0]


class _Win32Point(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class _Win32Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _list_windows_win32(user32=None) -> tuple[WindowInfo, ...]:
    ensure_capture_coordinate_space()
    user32 = user32 or ctypes.windll.user32
    windows: list[WindowInfo] = []

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        is_iconic = getattr(user32, "IsIconic", None)
        if callable(is_iconic) and is_iconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        rects = _client_and_window_rect(user32, hwnd)
        if rects is None:
            return True
        client_rect, window_rect = rects
        windows.append(
            WindowInfo(
                title=title,
                identifier=str(int(hwnd)),
                rect=client_rect,
                window_rect=window_rect,
            )
        )
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    return tuple(windows)


def _client_and_window_rect(user32, hwnd) -> tuple[CaptureRect, CaptureRect] | None:
    window_rect = _Win32Rect()
    if not user32.GetWindowRect(hwnd, ctypes.byref(window_rect)):
        return None
    client_rect = _Win32Rect()
    if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
        return None
    client_origin = _Win32Point(int(client_rect.left), int(client_rect.top))
    if not user32.ClientToScreen(hwnd, ctypes.byref(client_origin)):
        return None
    client_width = int(client_rect.right - client_rect.left)
    client_height = int(client_rect.bottom - client_rect.top)
    window_width = int(window_rect.right - window_rect.left)
    window_height = int(window_rect.bottom - window_rect.top)
    if client_width <= 0 or client_height <= 0 or window_width <= 0 or window_height <= 0:
        return None
    return (
        CaptureRect(
            left=int(client_origin.x),
            top=int(client_origin.y),
            width=client_width,
            height=client_height,
        ),
        CaptureRect(
            left=int(window_rect.left),
            top=int(window_rect.top),
            width=window_width,
            height=window_height,
        ),
    )
