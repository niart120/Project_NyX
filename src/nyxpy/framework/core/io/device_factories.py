"""Runtime 用 device port factory。"""

from collections.abc import Callable
from threading import Lock
from typing import Any

from nyxpy.framework.core.hardware.capture import CameraCaptureDevice, DummyCaptureDevice
from nyxpy.framework.core.hardware.capture_source import (
    CameraCaptureSourceConfig,
    CaptureSourceConfig,
    CaptureSourceKey,
    WindowCaptureSourceConfig,
)
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceDiscoveryService,
    DeviceInfo,
)
from nyxpy.framework.core.hardware.frame_transform import FrameTransformer
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.serial_comm import (
    DummySerialComm,
    SerialComm,
    SerialCommInterface,
)
from nyxpy.framework.core.hardware.window_capture import (
    WindowCaptureBackend,
    WindowCaptureDevice,
)
from nyxpy.framework.core.hardware.window_discovery import WindowLocatorBackend
from nyxpy.framework.core.io.adapters import CaptureFrameSourcePort, SerialControllerOutputPort
from nyxpy.framework.core.io.ports import ControllerOutputPort, FrameSourcePort
from nyxpy.framework.core.logger import LoggerPort, NullLoggerPort
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class ControllerOutputPortFactory:
    """シリアル device 設定から controller output port を生成します。"""

    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        protocol: SerialProtocolInterface,
        serial_factory: Callable[[str], SerialCommInterface] = SerialComm,
    ) -> None:
        """Device discovery、protocol、serial factory を保持します。"""
        self.discovery = discovery
        self.protocol = protocol
        self.serial_factory = serial_factory
        self._devices: dict[str, SerialCommInterface] = {}

    def create(
        self,
        *,
        name: str | None,
        baudrate: int | None,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> ControllerOutputPort:
        from nyxpy.framework.core.runtime.device_selection import (
            ConnectionRequest,
            ConnectionResolveStatus,
            select_serial_target,
        )

        del timeout_sec
        result = _last_discovery_result(self.discovery)
        selection = select_serial_target(
            ConnectionRequest(kind="serial", requested=name, allow_dummy=allow_dummy),
            result,
        )
        if selection.uses_dummy:
            return SerialControllerOutputPort(self._dummy_serial(), self.protocol)
        if selection.status == ConnectionResolveStatus.ERROR:
            raise _selection_error("serial", selection, _serial_device_labels_from_result(result))
        info = _selected_device(selection)
        device_key = str(info.identifier)
        device = self._devices.get(device_key)
        if device is None:
            device = self.serial_factory(str(info.identifier))
            open_device = getattr(device, "open")
            try:
                open_device(baudrate or 9600)
            except Exception as exc:
                if allow_dummy:
                    return SerialControllerOutputPort(self._dummy_serial(), self.protocol)
                raise _device_open_failed("serial", selection.requested, exc) from exc
            self._devices[device_key] = device
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

    def _dummy_serial(self) -> SerialCommInterface:
        device = self._devices.get(DUMMY_DEVICE_NAME)
        if device is None:
            device = DummySerialComm("dummy")
            device.open(9600)
            self._devices[DUMMY_DEVICE_NAME] = device
        return device


class FrameSourcePortFactory:
    """キャプチャ入力元設定から frame source port を生成します。"""

    def __init__(
        self,
        *,
        discovery: DeviceDiscoveryService,
        logger: LoggerPort | None = None,
        capture_factory: Callable[..., object] = CameraCaptureDevice,
        window_locator_factory: Callable[[], WindowLocatorBackend] | None = None,
        window_backend_factory: Callable[[str], WindowCaptureBackend] | None = None,
    ) -> None:
        """Device discovery と camera/window capture factory を保持します。"""
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
                return self._create_window_source(source, allow_dummy=allow_dummy)

    def _create_camera_source(
        self,
        *,
        source: CameraCaptureSourceConfig,
        allow_dummy: bool,
        timeout_sec: float,
    ) -> FrameSourcePort:
        from nyxpy.framework.core.runtime.device_selection import (
            ConnectionRequest,
            ConnectionResolveStatus,
            select_capture_target,
        )

        del timeout_sec
        device_name = _normalize_name(source.device_name)
        result = _last_discovery_result(self.discovery)
        selection = select_capture_target(
            ConnectionRequest(kind="capture", requested=device_name, allow_dummy=allow_dummy),
            result,
        )
        if selection.uses_dummy:
            cache_source = CameraCaptureSourceConfig(
                device_name=DUMMY_DEVICE_NAME,
                fps=source.fps,
                transform=source.transform,
            )
            cache_key = CaptureSourceKey.from_source(cache_source)
            return CaptureFrameSourcePort(self._dummy_capture(cache_key, source))
        if selection.status == ConnectionResolveStatus.ERROR:
            raise _selection_error("capture", selection, result.capture_names())
        info = _selected_device(selection)
        cache_source = CameraCaptureSourceConfig(
            device_name=info.name,
            fps=source.fps,
            transform=source.transform,
        )
        cache_key = CaptureSourceKey.from_source(cache_source)
        device = self._devices.get(cache_key)
        if device is None:
            kwargs = {
                "device_index": int(info.identifier),
                "fps": source.fps,
                "logger": self.logger,
            }
            if info.api_pref is not None:
                kwargs["api_pref"] = info.api_pref
            device = _SharedCaptureDevice(
                _TransformingCaptureDevice(
                    self.capture_factory(**kwargs),
                    transform=source.transform,
                )
            )
            self._devices[cache_key] = device
        if allow_dummy:
            dummy_key = CaptureSourceKey.from_source(
                CameraCaptureSourceConfig(
                    device_name=DUMMY_DEVICE_NAME,
                    fps=source.fps,
                    transform=source.transform,
                )
            )
            device = _FallbackCaptureDevice(
                device,
                self._dummy_capture(dummy_key, source),
                logger=self.logger,
            )
        return CaptureFrameSourcePort(device)

    def _create_window_source(
        self,
        source: WindowCaptureSourceConfig,
        *,
        allow_dummy: bool,
    ) -> FrameSourcePort:
        if not source.title_pattern.strip() and source.identifier in (None, ""):
            if allow_dummy:
                dummy_key = _dummy_capture_key(source.fps, source.transform)
                return CaptureFrameSourcePort(self._dummy_capture(dummy_key, source))
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
        if allow_dummy:
            device = _FallbackCaptureDevice(
                device,
                self._dummy_capture(_dummy_capture_key(source.fps, source.transform), source),
                logger=self.logger,
            )
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

    def _dummy_capture(
        self,
        cache_key: CaptureSourceKey,
        source: CameraCaptureSourceConfig | WindowCaptureSourceConfig,
    ) -> object:
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


class _FallbackCaptureDevice:
    def __init__(self, primary, fallback, *, logger: LoggerPort) -> None:
        self._primary = primary
        self._fallback = fallback
        self._logger = logger
        self._active = primary

    def __getattr__(self, name: str):
        return getattr(self._active, name)

    def initialize(self) -> None:
        try:
            self._primary.initialize()
        except Exception as exc:
            self._logger.technical(
                "WARNING",
                "Capture device initialization failed; falling back to dummy capture.",
                component="FrameSourcePortFactory",
                event="device.capture_fallback",
                exc=exc,
            )
            self._active = self._fallback
            self._fallback.initialize()
        else:
            self._active = self._primary

    def get_frame(self):
        return self._active.get_frame()

    def release(self) -> None:
        self._active.release()


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


def _dummy_capture_key(fps: float, transform) -> CaptureSourceKey:
    return CaptureSourceKey.from_source(
        CameraCaptureSourceConfig(
            device_name=DUMMY_DEVICE_NAME,
            fps=fps,
            transform=transform,
        )
    )


def _last_discovery_result(discovery: DeviceDiscoveryService) -> DeviceDiscoveryResult:
    last_result = getattr(discovery, "last_result", None)
    if isinstance(last_result, DeviceDiscoveryResult):
        return last_result
    serial_devices = _devices_tuple(getattr(discovery, "serial_devices", ()))
    capture_devices = _devices_tuple(getattr(discovery, "capture_devices", ()))
    return DeviceDiscoveryResult(
        serial_devices=serial_devices,
        capture_devices=capture_devices,
    )


def _devices_tuple(value: object) -> tuple[DeviceInfo, ...]:
    if isinstance(value, dict):
        return tuple(item for item in value.values() if isinstance(item, DeviceInfo))
    if isinstance(value, tuple):
        return tuple(item for item in value if isinstance(item, DeviceInfo))
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, DeviceInfo))
    return ()


def _serial_device_labels_from_result(result: DeviceDiscoveryResult) -> list[str]:
    return [
        f"{device.display_name} ({device.identifier})"
        if str(device.identifier) not in device.display_name
        else device.display_name
        for device in result.serial_devices
    ]


def _selected_device(selection: Any) -> DeviceInfo:
    selected = selection.selected
    if not isinstance(selected, DeviceInfo):
        raise RuntimeError("device selection did not contain a DeviceInfo")
    return selected


def _selection_error(
    device_type: str,
    selection: Any,
    available_devices: list[str],
) -> ConfigurationError:
    reason = selection.fallback_reason
    reason_text = str(reason) if reason is not None else None
    if reason_text == "not_selected":
        message = f"{device_type} device is not selected"
        code = "NYX_RUNTIME_DEVICE_NOT_SELECTED"
    elif reason_text == "user_selected_dummy":
        message = f"{device_type} dummy device is not allowed"
        code = "NYX_RUNTIME_DUMMY_DEVICE_NOT_ALLOWED"
    elif reason_text == "discovery_timed_out":
        message = f"{device_type} device discovery timed out"
        code = "NYX_RUNTIME_DEVICE_DISCOVERY_TIMED_OUT"
    else:
        message = f"{device_type} device '{selection.requested}' not found"
        code = "NYX_RUNTIME_DEVICE_NOT_FOUND"
    return ConfigurationError(
        message,
        code=code,
        component="MacroRuntimeBuilder",
        details={
            "device_type": device_type,
            "requested": selection.requested,
            "fallback_reason": reason_text,
            "available_devices": available_devices,
        },
    )


def _device_open_failed(
    device_type: str,
    requested: str | None,
    cause: Exception,
) -> ConfigurationError:
    return ConfigurationError(
        f"{device_type} device '{requested}' failed to open",
        code="NYX_RUNTIME_DEVICE_OPEN_FAILED",
        component="MacroRuntimeBuilder",
        details={
            "device_type": device_type,
            "requested": requested,
            "cause": f"{type(cause).__name__}: {cause}",
        },
    )
