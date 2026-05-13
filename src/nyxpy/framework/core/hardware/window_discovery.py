from __future__ import annotations

import ctypes
import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass

from nyxpy.framework.core.hardware.capture_source import CaptureRect, WindowCaptureSourceConfig
from nyxpy.framework.core.macro.exceptions import ConfigurationError


@dataclass(frozen=True)
class WindowInfo:
    title: str
    identifier: str | int
    rect: CaptureRect
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


def _list_windows_win32() -> tuple[WindowInfo, ...]:
    user32 = ctypes.windll.user32
    windows: list[WindowInfo] = []

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def callback(hwnd, _lparam) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        rect = Rect()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return True
        windows.append(
            WindowInfo(
                title=title,
                identifier=str(int(hwnd)),
                rect=CaptureRect(
                    left=int(rect.left),
                    top=int(rect.top),
                    width=width,
                    height=height,
                ),
            )
        )
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    return tuple(windows)
