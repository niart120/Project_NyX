from __future__ import annotations

import platform
import threading
from dataclasses import dataclass
from typing import Literal

import cv2
import serial.tools.list_ports
from cv2_enumerate_cameras import enumerate_cameras

from nyxpy.framework.core.hardware.window_discovery import (
    DefaultWindowLocatorBackend,
    WindowInfo,
)
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort

DUMMY_DEVICE_NAME = "ダミーデバイス"
DeviceKind = Literal["serial", "capture"]


@dataclass(frozen=True)
class DeviceInfo:
    kind: DeviceKind
    name: str
    identifier: str | int
    api_pref: int | None = None


@dataclass(frozen=True)
class DeviceDiscoveryResult:
    serial_devices: tuple[DeviceInfo, ...] = ()
    capture_devices: tuple[DeviceInfo, ...] = ()
    timed_out: bool = False
    errors: tuple[str, ...] = ()

    def serial_names(self) -> list[str]:
        return [device.name for device in self.serial_devices]

    def capture_names(self) -> list[str]:
        return [device.name for device in self.capture_devices]


class DeviceDiscoveryService:
    def __init__(self, *, logger: LoggerPort | None = None) -> None:
        self.logger = logger or NullLoggerPort()
        self.window_locator = DefaultWindowLocatorBackend()
        self._last_result = DeviceDiscoveryResult()
        self._lock = threading.Lock()

    @property
    def last_result(self) -> DeviceDiscoveryResult:
        with self._lock:
            return self._last_result

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
        if timeout_sec < 0:
            raise ValueError("timeout_sec must be greater than or equal to 0")
        result: tuple[WindowInfo, ...] | None = None
        errors: list[str] = []

        def worker() -> None:
            nonlocal result
            try:
                result = self.window_locator.list_windows()
            except Exception as exc:
                errors.append(f"window: {type(exc).__name__}: {exc}")
                self.logger.technical(
                    "WARNING",
                    "Window source discovery failed.",
                    component="DeviceDiscoveryService",
                    event="device.discovery_failed",
                    extra={"device_type": "window"},
                    exc=exc,
                )
                result = ()

        thread = threading.Thread(
            target=worker,
            name="nyx-window-discovery",
            daemon=True,
        )
        thread.start()
        thread.join(timeout_sec)
        if thread.is_alive():
            return ()
        return result or ()

    def find_serial(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self._find(name, "serial", timeout_sec)

    def find_capture(self, name: str, timeout_sec: float) -> DeviceInfo | None:
        return self._find(name, "capture", timeout_sec)

    def _find(self, name: str, kind: DeviceKind, timeout_sec: float) -> DeviceInfo | None:
        result = self.last_result
        devices = result.serial_devices if kind == "serial" else result.capture_devices
        match = next((device for device in devices if device.name == name), None)
        if match is not None:
            return match
        result = self.detect(timeout_sec)
        devices = result.serial_devices if kind == "serial" else result.capture_devices
        return next((device for device in devices if device.name == name), None)

    def _detect_serial_devices(self) -> list[DeviceInfo]:
        return [
            DeviceInfo(kind="serial", name=port.device, identifier=port.device)
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
        log_level = cv2.getLogLevel()
        cv2.setLogLevel(0)
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
            cv2.setLogLevel(log_level)
        return devices
