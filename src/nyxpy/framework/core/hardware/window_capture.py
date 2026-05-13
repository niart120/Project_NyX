from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import cv2
import numpy as np

from nyxpy.framework.core.hardware.capture import CaptureDeviceInterface
from nyxpy.framework.core.hardware.capture_source import (
    ScreenRegionCaptureSourceConfig,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.frame_transform import FrameTransformer
from nyxpy.framework.core.hardware.platform_capture import ensure_capture_coordinate_space
from nyxpy.framework.core.hardware.window_discovery import (
    DefaultWindowLocatorBackend,
    WindowLocatorBackend,
)
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort
from nyxpy.framework.core.macro.exceptions import ConfigurationError

if TYPE_CHECKING:
    from mss.base import MSSBase


class WindowCaptureSession(ABC):
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def latest_frame(self) -> cv2.typing.MatLike:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass


class WindowCaptureBackend(ABC):
    @abstractmethod
    def create_session(
        self,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> WindowCaptureSession:
        pass

    @abstractmethod
    def release(self) -> None:
        pass


class MssWindowCaptureBackend(WindowCaptureBackend):
    def create_session(
        self,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> WindowCaptureSession:
        return MssCaptureSession(config=config, locator=locator)

    def release(self) -> None:
        pass


class MssCaptureSession(WindowCaptureSession):
    def __init__(
        self,
        *,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
    ) -> None:
        self.config = config
        self.locator = locator
        self._mss: MSSBase | None = None

    def start(self) -> None:
        ensure_capture_coordinate_space()
        try:
            import mss
        except ImportError as exc:
            raise ConfigurationError(
                "mss is required for window or screen-region capture",
                code="NYX_CAPTURE_MSS_NOT_INSTALLED",
                component="MssCaptureSession",
                cause=exc,
            ) from exc
        self._mss = mss.mss()

    def latest_frame(self) -> cv2.typing.MatLike:
        if self._mss is None:
            raise RuntimeError("mss capture session is not started")
        monitor = self._monitor()
        raw = np.asarray(self._mss.grab(monitor))
        if raw.ndim != 3 or raw.shape[2] < 3:
            raise RuntimeError("mss returned an invalid frame")
        if raw.shape[2] == 4:
            return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        return raw[:, :, :3].copy()

    def stop(self) -> None:
        if self._mss is not None:
            self._mss.close()
            self._mss = None

    def _monitor(self) -> dict[str, int]:
        match self.config:
            case ScreenRegionCaptureSourceConfig():
                return self.config.region.to_mss_monitor()
            case WindowCaptureSourceConfig():
                if self.locator is None:
                    raise RuntimeError("window locator is required")
                return self.locator.resolve(self.config).rect.to_mss_monitor()


class ScreenRegionCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        config: ScreenRegionCaptureSourceConfig,
        *,
        backend: WindowCaptureBackend | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        self._device = _ThreadedSessionCaptureDevice(
            config=config,
            locator=None,
            backend=backend or _backend_for(config.backend),
            logger=logger,
        )

    def initialize(self) -> None:
        self._device.initialize()

    def get_frame(self) -> cv2.typing.MatLike:
        return self._device.get_frame()

    def release(self) -> None:
        self._device.release()


class WindowCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        config: WindowCaptureSourceConfig,
        *,
        locator: WindowLocatorBackend | None = None,
        backend: WindowCaptureBackend | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        self._device = _ThreadedSessionCaptureDevice(
            config=config,
            locator=locator or DefaultWindowLocatorBackend(),
            backend=backend or _backend_for(config.backend),
            logger=logger,
        )

    def initialize(self) -> None:
        self._device.initialize()

    def get_frame(self) -> cv2.typing.MatLike:
        return self._device.get_frame()

    def release(self) -> None:
        self._device.release()


class _ThreadedSessionCaptureDevice(CaptureDeviceInterface):
    def __init__(
        self,
        *,
        config: WindowCaptureSourceConfig | ScreenRegionCaptureSourceConfig,
        locator: WindowLocatorBackend | None,
        backend: WindowCaptureBackend,
        logger: LoggerPort | None,
    ) -> None:
        self.config = config
        self.locator = locator
        self.backend = backend
        self.logger = logger or NullLoggerPort()
        self._transformer = FrameTransformer()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest_frame: cv2.typing.MatLike | None = None
        self._last_error: Exception | None = None
        self._start_error: Exception | None = None
        self._ready = threading.Event()

    def initialize(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"nyx-{self.config.source_type}-capture",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=2.0):
            self.release()
            raise RuntimeError(f"{self.config.source_type} capture did not start")
        if self._start_error is not None:
            error = self._start_error
            self.release()
            raise RuntimeError(f"{self.config.source_type} capture failed to start") from error

    def get_frame(self) -> cv2.typing.MatLike:
        with self._lock:
            if self._latest_frame is None:
                raise RuntimeError(f"{self.config.source_type} capture has no frame available yet")
            return self._latest_frame.copy()

    def release(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.backend.release()

    def _capture_loop(self) -> None:
        session = self.backend.create_session(self.config, self.locator)
        interval = 1.0 / self.config.fps if self.config.fps > 0 else 1.0 / 30.0
        try:
            session.start()
        except Exception as exc:
            self._start_error = exc
            self._ready.set()
            return
        self._ready.set()
        consecutive_failures = 0
        resolve_deadline: float | None = None
        try:
            while self._running:
                begin = time.perf_counter()
                try:
                    frame = session.latest_frame()
                    transformed = self._transformer.transform(frame, self.config.transform)
                    with self._lock:
                        self._latest_frame = transformed.copy()
                    consecutive_failures = 0
                    resolve_deadline = None
                except Exception as exc:
                    consecutive_failures += 1
                    self._last_error = exc
                    if consecutive_failures >= 3:
                        with self._lock:
                            self._latest_frame = None
                        resolve_deadline = resolve_deadline or time.monotonic() + 10.0
                        if time.monotonic() >= resolve_deadline:
                            self.logger.technical(
                                "ERROR",
                                "Capture source could not be resolved.",
                                component=type(self).__name__,
                                event="capture.source_lost",
                                exc=exc,
                            )
                            self._running = False
                            break
                elapsed = time.perf_counter() - begin
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        finally:
            try:
                session.stop()
            except Exception as exc:
                self.logger.technical(
                    "WARNING",
                    "Capture session cleanup failed.",
                    component=type(self).__name__,
                    event="resource.cleanup_failed",
                    exc=exc,
                )


def _backend_for(name: str) -> WindowCaptureBackend:
    if name in ("auto", "mss"):
        return MssWindowCaptureBackend()
    if name == "windows_graphics_capture":
        raise ConfigurationError(
            "windows_graphics_capture backend is not implemented in the MVP",
            code="NYX_CAPTURE_BACKEND_UNAVAILABLE",
            component="WindowCaptureBackend",
        )
    raise ConfigurationError(
        "invalid capture backend",
        code="NYX_CAPTURE_BACKEND_INVALID",
        component="WindowCaptureBackend",
        details={"backend": name},
    )
