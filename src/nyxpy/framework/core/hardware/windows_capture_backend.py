from __future__ import annotations

import platform
import sys
import threading
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from nyxpy.framework.core.hardware.capture_source import (
    ScreenRegionCaptureSourceConfig,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.window_capture import WindowCaptureBackend, WindowCaptureSession
from nyxpy.framework.core.hardware.window_discovery import WindowLocatorBackend
from nyxpy.framework.core.macro.exceptions import ConfigurationError

type CaptureClassFactory = Callable[[], type]


class WindowsGraphicsCaptureBackend(WindowCaptureBackend):
    def __init__(
        self,
        *,
        capture_class_factory: CaptureClassFactory | None = None,
        platform_name: str | None = None,
        windows_build: int | None = None,
    ) -> None:
        self._capture_class_factory = capture_class_factory or _import_windows_capture
        self._platform_name = platform_name
        self._windows_build = windows_build

    def create_session(
        self,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> WindowCaptureSession:
        if isinstance(config, ScreenRegionCaptureSourceConfig):
            raise ConfigurationError(
                "windows_graphics_capture supports window sources only",
                code="NYX_CAPTURE_BACKEND_INVALID_SOURCE",
                component=type(self).__name__,
            )
        if locator is None:
            raise ConfigurationError(
                "window locator is required for windows_graphics_capture",
                code="NYX_CAPTURE_WINDOW_NOT_SELECTED",
                component=type(self).__name__,
            )
        return WindowsGraphicsCaptureSession(
            config=config,
            locator=locator,
            capture_class_factory=self._capture_class_factory,
            platform_name=self._platform_name,
            windows_build=self._windows_build,
        )

    def release(self) -> None:
        pass


class WindowsGraphicsCaptureSession(WindowCaptureSession):
    def __init__(
        self,
        *,
        config: WindowCaptureSourceConfig,
        locator: WindowLocatorBackend,
        capture_class_factory: CaptureClassFactory | None = None,
        platform_name: str | None = None,
        windows_build: int | None = None,
    ) -> None:
        self.config = config
        self.locator = locator
        self._capture_class_factory = capture_class_factory or _import_windows_capture
        self._platform_name = platform_name
        self._windows_build = windows_build
        self._lock = threading.Lock()
        self._latest_frame: cv2.typing.MatLike | None = None
        self._capture_control: Any | None = None
        self._closed = False

    def start(self) -> None:
        self._check_platform()
        capture_class = self._capture_class_factory()
        window = self.locator.resolve(self.config)
        hwnd = _window_hwnd(self.config.identifier) or _window_hwnd(window.identifier)
        capture = capture_class(
            cursor_capture=False,
            draw_border=False,
            monitor_index=None,
            window_name=None if hwnd is not None else window.title,
            window_hwnd=hwnd,
            minimum_update_interval=max(int(1000 / self.config.fps), 1),
        )

        @capture.event
        def on_frame_arrived(frame, _capture_control) -> None:
            raw = np.asarray(frame.frame_buffer)
            if raw.ndim != 3 or raw.shape[2] < 3:
                raise RuntimeError("windows-capture returned an invalid frame")
            bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR) if raw.shape[2] == 4 else raw[:, :, :3]
            with self._lock:
                self._latest_frame = bgr.copy()

        @capture.event
        def on_closed() -> None:
            self._closed = True

        self._capture_control = capture.start_free_threaded()

    def latest_frame(self) -> cv2.typing.MatLike:
        if self._closed:
            raise RuntimeError("windows graphics capture session is closed")
        with self._lock:
            if self._latest_frame is None:
                raise RuntimeError("windows graphics capture frame is not ready")
            return self._latest_frame.copy()

    def stop(self) -> None:
        control = self._capture_control
        self._capture_control = None
        if control is None:
            return
        stop = getattr(control, "stop", None)
        if callable(stop):
            stop()
        wait = getattr(control, "wait", None)
        if callable(wait):
            wait()

    def _check_platform(self) -> None:
        platform_name = self._platform_name or platform.system()
        if platform_name != "Windows":
            raise ConfigurationError(
                "windows_graphics_capture is supported only on Windows",
                code="NYX_CAPTURE_BACKEND_UNSUPPORTED_PLATFORM",
                component=type(self).__name__,
                details={"platform": platform_name},
            )
        build = self._windows_build if self._windows_build is not None else _windows_build()
        if build is not None and build < 18362:
            raise ConfigurationError(
                "windows_graphics_capture requires Windows 10 version 1903 or later",
                code="NYX_CAPTURE_BACKEND_UNSUPPORTED_VERSION",
                component=type(self).__name__,
                details={"windows_build": build},
            )


def _import_windows_capture() -> type:
    try:
        from windows_capture import WindowsCapture
    except ImportError as exc:
        raise ConfigurationError(
            "windows-capture optional dependency is required for windows_graphics_capture",
            code="NYX_CAPTURE_WINDOWS_CAPTURE_NOT_INSTALLED",
            component="WindowsGraphicsCaptureBackend",
            cause=exc,
        ) from exc
    return WindowsCapture


def _windows_build() -> int | None:
    version = getattr(sys, "getwindowsversion", None)
    if version is None:
        return None
    return int(version().build)


def _window_hwnd(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        hwnd = int(str(value), 0)
    except (TypeError, ValueError):
        return None
    return hwnd if hwnd > 0 else None
