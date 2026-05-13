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
    process_id: int | None = None
    app_name: str | None = None

    @property
    def display_name(self) -> str:
        pid = f" pid={self.process_id}" if self.process_id is not None else ""
        return f"{self.title}{pid}"


@dataclass(frozen=True)
class WindowDiscoveryDiagnostics:
    platform_name: str
    total_handles: int = 0
    visible_handles: int = 0
    titled_handles: int = 0
    valid_rect_handles: int = 0
    returned_windows: int = 0
    error: str = ""

    def summary(self) -> str:
        if self.error:
            return f"platform={self.platform_name} error={self.error}"
        return (
            f"platform={self.platform_name} total={self.total_handles} "
            f"visible={self.visible_handles} titled={self.titled_handles} "
            f"rect={self.valid_rect_handles} returned={self.returned_windows}"
        )


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
        windows, _diagnostics = _list_windows_win32()
        return windows

    def diagnostics(self) -> WindowDiscoveryDiagnostics:
        platform_name = platform.system()
        if platform_name != "Windows":
            return WindowDiscoveryDiagnostics(platform_name=platform_name)
        try:
            _windows, diagnostics = _list_windows_win32()
        except Exception as exc:
            return WindowDiscoveryDiagnostics(
                platform_name=platform_name,
                error=f"{type(exc).__name__}: {exc}",
            )
        return diagnostics


def resolve_window(
    windows: tuple[WindowInfo, ...],
    config: WindowCaptureSourceConfig,
) -> WindowInfo:
    if config.identifier not in (None, ""):
        identifier = str(config.identifier)
        for window in windows:
            if str(window.identifier) == identifier and _pid_matches(window, config.process_id):
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
    if config.process_id is not None:
        matches = [window for window in matches if window.process_id == config.process_id]
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


def _pid_matches(window: WindowInfo, process_id: int | None) -> bool:
    return process_id is None or window.process_id == process_id


def _list_windows_win32() -> tuple[tuple[WindowInfo, ...], WindowDiscoveryDiagnostics]:
    user32 = ctypes.windll.user32
    windows: list[WindowInfo] = []
    total_handles = 0
    visible_handles = 0
    titled_handles = 0
    valid_rect_handles = 0

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def callback(hwnd, _lparam) -> bool:
        nonlocal total_handles, visible_handles, titled_handles, valid_rect_handles
        total_handles += 1
        if not user32.IsWindowVisible(hwnd):
            return True
        visible_handles += 1
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True
        titled_handles += 1
        rect = Rect()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width <= 0 or height <= 0:
            return True
        valid_rect_handles += 1
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
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
                process_id=int(pid.value) if pid.value else None,
            )
        )
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    detected = tuple(windows)
    return detected, WindowDiscoveryDiagnostics(
        platform_name="Windows",
        total_handles=total_handles,
        visible_handles=visible_handles,
        titled_handles=titled_handles,
        valid_rect_handles=valid_rect_handles,
        returned_windows=len(detected),
    )
