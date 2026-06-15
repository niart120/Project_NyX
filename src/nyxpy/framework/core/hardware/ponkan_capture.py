"""ponkan-python を使う直接接続型 capture device adapter。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from importlib import import_module
from typing import Protocol, cast, override

import cv2

from nyxpy.framework.core.hardware.camera_capture import (
    CaptureDeviceInterface,
    CaptureDeviceNotReady,
    CaptureDeviceReadFailed,
)
from nyxpy.framework.core.hardware.capture_source import PonkanCaptureSourceConfig
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class PonkanReader(Protocol):
    """ponkan CaptureReader のうち NyX adapter が使う surface。"""

    def read(
        self,
        *,
        output: object | str | None = None,
        colorspace: str | None = None,
        timeout: float | None = None,
    ) -> cv2.typing.MatLike | None: ...

    def stats(self) -> object: ...

    def close(self) -> None: ...


type PonkanOpenCapture = Callable[[PonkanCaptureSourceConfig], PonkanReader]


class PonkanCaptureDevice(CaptureDeviceInterface):
    """ponkan reader を `CaptureDeviceInterface` として扱う adapter。"""

    def __init__(
        self,
        config: PonkanCaptureSourceConfig,
        *,
        opener: PonkanOpenCapture | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        """Ponkan source 設定、reader opener、ログ出力先を保持します。"""
        self.config = config
        self._opener = opener or _open_ponkan_capture
        self._logger = logger or NullLoggerPort()
        self._reader: PonkanReader | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest_frame: cv2.typing.MatLike | None = None
        self._fatal_error: BaseException | None = None
        self._running = False
        self._released = False

    @override
    def initialize(self) -> None:
        """Ponkan reader を開き、最新 frame cache 更新 thread を開始します。"""
        if self._running:
            return
        self._released = False
        self._fatal_error = None
        self._reader = self._opener(self.config)
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"nyx-ponkan-{self.config.device_profile}-capture",
            daemon=True,
        )
        self._thread.start()

    @override
    def get_frame(self) -> cv2.typing.MatLike:
        """Cache 済み最新 frame の copy を返します。"""
        with self._lock:
            if self._fatal_error is not None:
                raise CaptureDeviceReadFailed("ponkan capture reader failed") from self._fatal_error
            if self._latest_frame is None:
                raise CaptureDeviceNotReady("ponkan capture has no frame available yet")
            return self._latest_frame.copy()

    @override
    def release(self) -> None:
        """Reader thread と ponkan reader を解放します。"""
        if self._released:
            return
        self._released = True
        self._running = False
        reader = self._reader
        self._reader = None
        if reader is not None:
            try:
                reader.close()
            except Exception as exc:
                self._logger.technical(
                    "WARNING",
                    "Ponkan capture reader cleanup failed.",
                    component=type(self).__name__,
                    event="resource.cleanup_failed",
                    exc=exc,
                )
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _read_loop(self) -> None:
        reader = self._reader
        if reader is None:
            return
        while self._running:
            try:
                frame = reader.read(
                    output="both_vertical",
                    colorspace="BGR",
                    timeout=self.config.read_timeout,
                )
            except Exception as exc:
                if not self._running:
                    return
                with self._lock:
                    self._fatal_error = exc
                    self._latest_frame = None
                self._logger.technical(
                    "ERROR",
                    "Ponkan capture reader failed.",
                    component=type(self).__name__,
                    event="capture.read_failed",
                    exc=exc,
                )
                self._running = False
                return
            if frame is None:
                time.sleep(self.config.poll_interval)
                continue
            with self._lock:
                self._latest_frame = frame.copy()


def _open_ponkan_capture(config: PonkanCaptureSourceConfig) -> PonkanReader:
    try:
        ponkan = import_module("ponkan")
        ponkan_errors = import_module("ponkan.errors")
    except ImportError as exc:
        raise ConfigurationError(
            "ponkan-python is required for capture source",
            code="NYX_PONKAN_CAPTURE_DEPENDENCY_MISSING",
            component="PonkanCaptureDevice",
            details={"extra": "ponkan", "provider": config.provider},
            cause=exc,
        ) from exc

    try:
        capture_config = getattr(ponkan, "CaptureConfig")
        capture_output = getattr(ponkan, "CaptureOutput")
        get_capture_profile = getattr(ponkan, "get_capture_profile")
        open_capture = getattr(ponkan, "open_capture")
        capture_error = getattr(ponkan_errors, "CaptureError")
        dependency_unavailable_error = getattr(ponkan_errors, "DependencyUnavailableError")
    except AttributeError as exc:
        raise ConfigurationError(
            "ponkan-python 0.2.0 or later is required for capture source",
            code="NYX_PONKAN_CAPTURE_API_UNSUPPORTED",
            component="PonkanCaptureDevice",
            details={
                "extra": "ponkan",
                "provider": config.provider,
                "profile": config.device_profile,
                "cause": type(exc).__name__,
            },
            cause=exc,
        ) from exc

    try:
        profile = get_capture_profile(config.device_profile)
    except capture_error as exc:
        raise ConfigurationError(
            "invalid ponkan capture profile",
            code="NYX_PONKAN_CAPTURE_PROFILE_INVALID",
            component="PonkanCaptureDevice",
            recoverable=_upstream_recoverable(exc),
            details=_ponkan_error_details(
                exc,
                backend=config.ponkan_backend,
                profile=config.device_profile,
            ),
            cause=exc,
        ) from exc

    ponkan_config = capture_config(
        source=getattr(profile, "model", "new_3ds_xl"),
        model=getattr(profile, "model", "new_3ds_xl"),
        backend=config.ponkan_backend,
        output=capture_output.BOTH_VERTICAL,
        colorspace="BGR",
        raw_slots=config.raw_slots,
        output_queue_size=config.output_queue_size,
        drop_policy=config.drop_policy,
        poll_interval=config.poll_interval,
        read_timeout=config.read_timeout,
        collect_timing=config.collect_timing,
    )
    try:
        return cast(PonkanReader, open_capture(config=ponkan_config))
    except dependency_unavailable_error as exc:
        raise ConfigurationError(
            "ponkan capture dependency is unavailable",
            code="NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE",
            component="PonkanCaptureDevice",
            recoverable=_upstream_recoverable(exc),
            details=_ponkan_error_details(
                exc,
                backend=config.ponkan_backend,
                profile=config.device_profile,
            ),
            cause=exc,
        ) from exc
    except capture_error as exc:
        raise ConfigurationError(
            "failed to open ponkan capture source",
            code="NYX_PONKAN_CAPTURE_OPEN_FAILED",
            component="PonkanCaptureDevice",
            recoverable=_upstream_recoverable(exc),
            details=_ponkan_error_details(
                exc,
                backend=config.ponkan_backend,
                profile=config.device_profile,
            ),
            cause=exc,
        ) from exc


def _ponkan_error_details(
    exc: BaseException,
    *,
    backend: str,
    profile: str,
) -> dict[str, str | int | float | bool | None]:
    details: dict[str, str | int | float | bool | None] = {
        "backend": backend,
        "profile": profile,
        "cause": type(exc).__name__,
    }
    for key in ("code", "profile", "backend", "reason", "recoverable", "remediation"):
        value = getattr(exc, key, None)
        details[f"upstream_{key}"] = _detail_scalar(value)
    return details


def _upstream_recoverable(exc: BaseException) -> bool:
    value = getattr(exc, "recoverable", False)
    return bool(value)


def _detail_scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
