"""キャプチャデバイスとシリアルデバイスの検出 service。"""

from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

import cv2
import serial.tools.list_ports
from cv2_enumerate_cameras import enumerate_cameras

from nyxpy.framework.core.hardware.ponkan_discovery import (
    PonkanCaptureDeviceDescriptor,
    PonkanCaptureDiscoverySnapshot,
    list_ponkan_capture_devices,
)
from nyxpy.framework.core.hardware.window_discovery import (
    DefaultWindowLocatorBackend,
    WindowInfo,
)
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort

DUMMY_DEVICE_NAME = "ダミーデバイス"
DeviceKind = Literal["serial", "capture"]


@dataclass(frozen=True)
class DeviceInfo:
    """GUI/CLI へ提示する検出済み device の情報。"""

    kind: DeviceKind
    name: str
    identifier: str | int
    api_pref: int | None = None

    @property
    def display_name(self) -> str:
        return self.name


@dataclass(frozen=True)
class DeviceDiscoveryResult:
    """シリアル・キャプチャ device 検出の結果。"""

    serial_devices: tuple[DeviceInfo, ...] = ()
    capture_devices: tuple[DeviceInfo, ...] = ()
    timed_out: bool = False
    errors: tuple[str, ...] = ()

    def serial_names(self) -> list[str]:
        return [device.name for device in self.serial_devices]

    def capture_names(self) -> list[str]:
        return [device.name for device in self.capture_devices]


@dataclass(frozen=True)
class WindowDiscoveryResult:
    """Window capture 候補検出の結果。"""

    window_sources: tuple[WindowInfo, ...] = ()
    failed: bool = False
    errors: tuple[str, ...] = ()


class DeviceDiscoveryService:
    """シリアル、カメラ、window capture 候補を検出します。"""

    def __init__(self, *, logger: LoggerPort | None = None) -> None:
        """ログ出力先と window locator を準備し、直近結果を初期化します。"""
        self.logger = logger or NullLoggerPort()
        self.window_locator = DefaultWindowLocatorBackend()
        self._last_result = DeviceDiscoveryResult()
        self._last_window_sources: tuple[WindowInfo, ...] = ()
        self._last_ponkan_capture_discovery = PonkanCaptureDiscoverySnapshot()
        self._lock = threading.Lock()

    @property
    def last_result(self) -> DeviceDiscoveryResult:
        with self._lock:
            return self._last_result

    @property
    def last_window_sources(self) -> tuple[WindowInfo, ...]:
        """直近に検出した window capture 候補を返します。"""
        with self._lock:
            return self._last_window_sources

    @property
    def last_ponkan_capture_discovery(self) -> PonkanCaptureDiscoverySnapshot:
        """Return the latest ponkan capture discovery snapshot."""
        with self._lock:
            return self._last_ponkan_capture_discovery

    def detect(self, timeout_sec: float = 2.0) -> DeviceDiscoveryResult:
        if timeout_sec < 0:
            raise ValueError("timeout_sec must be greater than or equal to 0")
        result: DeviceDiscoveryResult | None = None

        def worker() -> None:
            nonlocal result
            errors: list[str] = []
            try:
                serial_devices = tuple(self._detect_serial_devices())
            except Exception as exc:
                errors.append(f"serial: {type(exc).__name__}: {exc}")
                self.logger.technical(
                    "WARNING",
                    "Serial device discovery failed.",
                    component="DeviceDiscoveryService",
                    event="device.discovery_failed",
                    extra={"device_type": "serial"},
                    exc=exc,
                )
                serial_devices = ()
            try:
                capture_devices = tuple(self._detect_capture_devices())
            except Exception as exc:
                errors.append(f"capture: {type(exc).__name__}: {exc}")
                self.logger.technical(
                    "WARNING",
                    "Capture device discovery failed.",
                    component="DeviceDiscoveryService",
                    event="device.discovery_failed",
                    extra={"device_type": "capture"},
                    exc=exc,
                )
                capture_devices = ()
            result = DeviceDiscoveryResult(
                serial_devices=serial_devices,
                capture_devices=capture_devices,
                errors=tuple(errors),
            )

        thread = threading.Thread(target=worker, name="nyx-device-discovery", daemon=True)
        thread.start()
        thread.join(timeout_sec)
        if thread.is_alive():
            detected = DeviceDiscoveryResult(timed_out=True)
        else:
            detected = result or DeviceDiscoveryResult()
        with self._lock:
            self._last_result = detected
        return detected

    def serial_names(self) -> list[str]:
        return self.last_result.serial_names()

    def capture_names(self) -> list[str]:
        return self.last_result.capture_names()

    def detect_window_sources(self, timeout_sec: float = 2.0) -> tuple[WindowInfo, ...]:
        return self.detect_window_sources_result(timeout_sec=timeout_sec).window_sources

    def detect_ponkan_capture_devices(
        self,
        *,
        timeout_sec: float = 2.0,
        profile: str = "n3dsxl",
        backend: str = "auto",
        include_rejected: bool = False,
    ) -> tuple[PonkanCaptureDeviceDescriptor, ...]:
        """Return visible ponkan capture device descriptors."""
        return self.detect_ponkan_capture_devices_result(
            timeout_sec=timeout_sec,
            profile=profile,
            backend=backend,
            include_rejected=include_rejected,
        ).devices

    def detect_ponkan_capture_devices_result(
        self,
        *,
        timeout_sec: float = 2.0,
        profile: str = "n3dsxl",
        backend: str = "auto",
        include_rejected: bool = False,
    ) -> PonkanCaptureDiscoverySnapshot:
        """Return structured ponkan capture discovery state."""
        if timeout_sec < 0:
            raise ValueError("timeout_sec must be greater than or equal to 0")
        result: PonkanCaptureDiscoverySnapshot | None = None

        def worker() -> None:
            nonlocal result
            result = list_ponkan_capture_devices(
                profile=profile,
                backend=backend,
                include_rejected=include_rejected,
            )

        thread = threading.Thread(target=worker, name="nyx-ponkan-discovery", daemon=True)
        thread.start()
        thread.join(timeout_sec)
        if thread.is_alive():
            detected = PonkanCaptureDiscoverySnapshot(
                profile_id=profile,
                backend_preference=backend,
                timed_out=True,
                errors=("ponkan: discovery timed out",),
            )
        else:
            detected = result or PonkanCaptureDiscoverySnapshot(
                profile_id=profile,
                backend_preference=backend,
            )
        with self._lock:
            self._last_ponkan_capture_discovery = detected
        return detected

    def detect_window_sources_result(
        self,
        timeout_sec: float = 2.0,
    ) -> WindowDiscoveryResult:
        if timeout_sec < 0:
            raise ValueError("timeout_sec must be greater than or equal to 0")
        started_at = time.perf_counter()
        try:
            detected = self.window_locator.list_windows()
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "Window source discovery failed.",
                component="DeviceDiscoveryService",
                event="device.discovery_failed",
                extra={"device_type": "window"},
                exc=exc,
            )
            return WindowDiscoveryResult(
                failed=True,
                errors=(f"window: {type(exc).__name__}: {exc}",),
            )
        elapsed_sec = time.perf_counter() - started_at
        self.logger.technical(
            "INFO",
            "Window source discovery completed.",
            component="DeviceDiscoveryService",
            event="device.window_discovery_completed",
            extra={
                "count": len(detected),
                "titles": [window.title for window in detected[:5]],
                "elapsed_sec": elapsed_sec,
            },
        )
        if elapsed_sec > timeout_sec:
            self.logger.technical(
                "WARNING",
                "Window source discovery exceeded timeout budget.",
                component="DeviceDiscoveryService",
                event="device.window_discovery_slow",
                extra={"timeout_sec": timeout_sec, "elapsed_sec": elapsed_sec},
            )
        with self._lock:
            self._last_window_sources = detected
        return WindowDiscoveryResult(window_sources=detected)

    def serial_display_name(self, identifier: str) -> str:
        match = next(
            (
                device
                for device in self.last_result.serial_devices
                if str(device.identifier) == str(identifier)
            ),
            None,
        )
        return match.display_name if match is not None else identifier

    def _detect_serial_devices(self) -> list[DeviceInfo]:
        return [
            DeviceInfo(
                kind="serial",
                name=_serial_display_name(port),
                identifier=port.device,
            )
            for port in serial.tools.list_ports.comports()
        ]

    def _detect_capture_devices(self) -> list[DeviceInfo]:
        os_name = platform.system()
        match os_name:
            case "Windows":
                return [
                    DeviceInfo(
                        kind="capture",
                        name=f"{camera_info.index}: {camera_info.name}",
                        identifier=camera_info.index,
                        api_pref=cv2.CAP_DSHOW,
                    )
                    for camera_info in enumerate_cameras(cv2.CAP_DSHOW)
                ]
            case "Linux":
                return [
                    DeviceInfo(
                        kind="capture",
                        name=f"{camera_info.index}: {camera_info.name}",
                        identifier=camera_info.index,
                        api_pref=cv2.CAP_V4L2,
                    )
                    for camera_info in enumerate_cameras(cv2.CAP_V4L2)
                ]
            case "Darwin":
                return self._detect_macos_capture_devices()
            case _:
                return []

    def _detect_macos_capture_devices(self) -> list[DeviceInfo]:
        devices: list[DeviceInfo] = []
        get_log_level = getattr(cv2, "getLogLevel", None)
        set_log_level = getattr(cv2, "setLogLevel", None)
        log_level: Any | None = get_log_level() if callable(get_log_level) else None
        if callable(set_log_level):
            set_log_level(0)
        try:
            for index in range(5):
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    devices.append(
                        DeviceInfo(
                            kind="capture",
                            name=f"macOS Camera {index}",
                            identifier=index,
                        )
                    )
                cap.release()
        finally:
            if callable(set_log_level) and log_level is not None:
                set_log_level(log_level)
        return devices


def _serial_display_name(port) -> str:
    device = str(getattr(port, "device", "") or "")
    description = str(
        getattr(port, "description", "") or getattr(port, "name", "") or device
    ).strip()
    if not description or description == device:
        return device
    return f"{description} ({device})"
