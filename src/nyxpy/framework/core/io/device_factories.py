from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from nyxpy.framework.core.hardware.capture import CameraCaptureDevice, DummyCaptureDevice
from nyxpy.framework.core.hardware.capture_source import (
    CameraCaptureSourceConfig,
    CaptureSourceConfig,
    CaptureSourceKey,
    ScreenRegionCaptureSourceConfig,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryService,
    DeviceInfo,
)
from nyxpy.framework.core.hardware.frame_transform import FrameTransformer
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.serial_comm import DummySerialComm, SerialComm
from nyxpy.framework.core.hardware.window_capture import (
    ScreenRegionCaptureDevice,
    WindowCaptureBackend,
    WindowCaptureDevice,
)
from nyxpy.framework.core.hardware.window_discovery import WindowLocatorBackend
from nyxpy.framework.core.io.adapters import CaptureFrameSourcePort, SerialControllerOutputPort
from nyxpy.framework.core.io.ports import ControllerOutputPort, FrameSourcePort
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class ControllerOutputPortFactory:
    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        protocol: SerialProtocolInterface,
        serial_factory: Callable[[str], object] = SerialComm,
    ) -> None:
        self.discovery = discovery
        self.protocol = protocol
        self.serial_factory = serial_factory
        self._devices: dict[str, object] = {}

    def create(
        self,
        *,
        name: str | None,
        baudrate: int | None,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> ControllerOutputPort:
        device_name = _normalize_name(name)
        if device_name is None:
            if allow_dummy:
                device_name = DUMMY_DEVICE_NAME
            else:
                raise _device_not_selected("serial", self.discovery.serial_names())
        if device_name == DUMMY_DEVICE_NAME:
            if not allow_dummy:
                raise _dummy_not_allowed("serial")
            return SerialControllerOutputPort(self._dummy_serial(), self.protocol)
        info = self.discovery.find_serial(device_name, timeout_sec)
        if info is None:
            raise _device_not_found("serial", device_name, self.discovery.serial_names())
        device = self._devices.get(device_name)
        if device is None:
            device = self.serial_factory(str(info.identifier))
            open_device = getattr(device, "open")
            open_device(baudrate or 9600)
            self._devices[device_name] = device
        return SerialControllerOutputPort(device, self.protocol)

    def close(self) -> None:
        errors: list[Exception] = []
        for device in self._devices.values():
            try:
                device.close()
            except Exception as exc:
                errors.append(exc)
        self._devices.clear()
        if errors:
            raise ExceptionGroup("ControllerOutputPortFactory close failed", errors)

    def _dummy_serial(self) -> object:
        device = self._devices.get(DUMMY_DEVICE_NAME)
        if device is None:
            device = DummySerialComm("dummy")
            device.open(9600)
            self._devices[DUMMY_DEVICE_NAME] = device
        return device


class FrameSourcePortFactory:
    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        logger: LoggerPort | None = None,
        capture_factory: Callable[..., object] = CameraCaptureDevice,
        window_locator_factory: Callable[[], WindowLocatorBackend] | None = None,
        window_backend_factory: Callable[[str], WindowCaptureBackend] | None = None,
    ) -> None:
        self.discovery = discovery
        self.logger = logger or NullLoggerPort()
        self.capture_factory = capture_factory
        self.window_locator_factory = window_locator_factory
        self.window_backend_factory = window_backend_factory
        self._devices: dict[CaptureSourceKey, object] = {}

    def create(
        self,
        *,
        source: CaptureSourceConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> FrameSourcePort:
        match source:
            case CameraCaptureSourceConfig():
                return self._create_camera_source(
                    source=source,
                    allow_dummy=allow_dummy,
                    timeout_sec=timeout_sec,
                )
            case WindowCaptureSourceConfig():
                return self._create_window_source(source)
            case ScreenRegionCaptureSourceConfig():
                return self._create_screen_region_source(source)

    def _create_camera_source(
        self,
        *,
        source: CameraCaptureSourceConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> FrameSourcePort:
        device_name = _normalize_name(source.device_name)
        if device_name is None:
            if allow_dummy:
                device_name = DUMMY_DEVICE_NAME
            else:
                raise _device_not_selected("capture", self.discovery.capture_names())
        cache_source = CameraCaptureSourceConfig(
            device_name=device_name,
            fps=source.fps,
            transform=source.transform,
        )
        cache_key = CaptureSourceKey.from_source(cache_source)
        if device_name == DUMMY_DEVICE_NAME:
            if not allow_dummy:
                raise _dummy_not_allowed("capture")
            return CaptureFrameSourcePort(self._dummy_capture(cache_key, source))
        info = self.discovery.find_capture(device_name, timeout_sec)
        if info is None:
            info = _numeric_capture_info(device_name)
        if info is None:
            raise _device_not_found("capture", device_name, self.discovery.capture_names())
        device = self._devices.get(cache_key)
        if device is None:
            kwargs = {"device_index": int(info.identifier), "fps": source.fps, "logger": self.logger}
            if info.api_pref is not None:
                kwargs["api_pref"] = info.api_pref
            device = _SharedCaptureDevice(
                _TransformingCaptureDevice(
                    self.capture_factory(**kwargs),
                    transform=source.transform,
                )
            )
            self._devices[cache_key] = device
        return CaptureFrameSourcePort(device)

    def _create_window_source(self, source: WindowCaptureSourceConfig) -> FrameSourcePort:
        if not source.title_pattern.strip() and source.identifier in (None, ""):
            raise ConfigurationError(
                "capture window is not selected",
                code="NYX_CAPTURE_WINDOW_NOT_SELECTED",
                component="FrameSourcePortFactory",
            )
        cache_key = CaptureSourceKey.from_source(source)
        device = self._devices.get(cache_key)
        if device is None:
            device = _SharedCaptureDevice(
                WindowCaptureDevice(
                    source,
                    locator=self.window_locator_factory() if self.window_locator_factory else None,
                    backend=self.window_backend_factory(source.backend)
                    if self.window_backend_factory
                    else None,
                    logger=self.logger,
                )
            )
            self._devices[cache_key] = device
        return CaptureFrameSourcePort(device)

    def _create_screen_region_source(
        self,
        source: ScreenRegionCaptureSourceConfig,
    ) -> FrameSourcePort:
        cache_key = CaptureSourceKey.from_source(source)
        device = self._devices.get(cache_key)
        if device is None:
            device = _SharedCaptureDevice(
                ScreenRegionCaptureDevice(
                    source,
                    backend=self.window_backend_factory(source.backend)
                    if self.window_backend_factory
                    else None,
                    logger=self.logger,
                )
            )
            self._devices[cache_key] = device
        return CaptureFrameSourcePort(device)

    def close(self) -> None:
        errors: list[Exception] = []
        for device in self._devices.values():
            try:
                release = getattr(device, "release")
                release()
            except Exception as exc:
                errors.append(exc)
        self._devices.clear()
        if errors:
            raise ExceptionGroup("FrameSourcePortFactory close failed", errors)

    def _dummy_capture(self, cache_key: CaptureSourceKey, source: CameraCaptureSourceConfig) -> object:
        device = self._devices.get(cache_key)
        if device is None:
            device = _SharedCaptureDevice(
                _TransformingCaptureDevice(
                    DummyCaptureDevice(),
                    transform=source.transform,
                )
            )
            self._devices[cache_key] = device
        return device


class _SharedCaptureDevice:
    def __init__(self, device) -> None:
        self._device = device
        self._initialized = False
        self._lock = Lock()

    def __getattr__(self, name: str):
        return getattr(self._device, name)

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._device.initialize()
            self._initialized = True

    def get_frame(self):
        return self._device.get_frame()

    def release(self) -> None:
        with self._lock:
            if not self._initialized:
                return
            self._device.release()
            self._initialized = False


class _TransformingCaptureDevice:
    def __init__(self, device, *, transform) -> None:
        self._device = device
        self._transform = transform
        self._transformer = FrameTransformer()

    def __getattr__(self, name: str):
        return getattr(self._device, name)

    def initialize(self) -> None:
        self._device.initialize()

    def get_frame(self):
        return self._transformer.transform(self._device.get_frame(), self._transform)

    def release(self) -> None:
        self._device.release()


def _normalize_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _numeric_capture_info(name: str) -> DeviceInfo | None:
    if not name.isdigit():
        return None
    return DeviceInfo(kind="capture", name=name, identifier=int(name))


def _device_not_selected(device_type: str, available_devices: list[str]) -> ConfigurationError:
    return ConfigurationError(
        f"{device_type} device is not selected",
        code="NYX_RUNTIME_DEVICE_NOT_SELECTED",
        component="MacroRuntimeBuilder",
        details={"device_type": device_type, "available_devices": available_devices},
    )


def _device_not_found(
    device_type: str,
    name: str,
    available_devices: list[str],
) -> ConfigurationError:
    return ConfigurationError(
        f"{device_type} device '{name}' not found",
        code="NYX_RUNTIME_DEVICE_NOT_FOUND",
        component="MacroRuntimeBuilder",
        details={"device_type": device_type, "available_devices": available_devices},
    )


def _dummy_not_allowed(device_type: str) -> ConfigurationError:
    return ConfigurationError(
        f"{device_type} dummy device is not allowed",
        code="NYX_RUNTIME_DUMMY_DEVICE_NOT_ALLOWED",
        component="MacroRuntimeBuilder",
        details={"device_type": device_type},
    )
