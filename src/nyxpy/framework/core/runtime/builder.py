from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.io.adapters import (
    CaptureFrameSourcePort,
    NoopNotificationAdapter,
    NotificationHandlerAdapter,
    SerialControllerOutputPort,
)
from nyxpy.framework.core.io.ports import (
    ControllerOutputPort,
    FrameSourcePort,
    NotificationPort,
)
from nyxpy.framework.core.io.resources import (
    LocalResourceStore,
    LocalRunArtifactStore,
    MacroResourceScope,
    ResourceStorePort,
    RunArtifactStore,
)
from nyxpy.framework.core.logger.ports import (
    LoggerPort,
    RunLogContext,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.macro.registry import MacroDefinition, MacroRegistry
from nyxpy.framework.core.runtime.context import (
    ExecutionContext,
    RuntimeBuildRequest,
    RuntimeOptions,
    SettingsSnapshot,
)
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult
from nyxpy.framework.core.runtime.runtime import MacroRuntime
from nyxpy.framework.core.utils.cancellation import CancellationToken

type PortFactory[T] = Callable[[RuntimeBuildRequest, MacroDefinition], T]
type LifetimePortFactory[T] = Callable[[], T]
type ArtifactStoreFactory = Callable[[RuntimeBuildRequest, MacroDefinition, str], RunArtifactStore]

DUMMY_DEVICE_NAME = "ダミーデバイス"


class MacroRuntimeBuilder:
    def __init__(
        self,
        *,
        project_root: Path,
        registry: MacroRegistry,
        settings: SettingsSnapshot | None = None,
        runtime: MacroRuntime | None = None,
        controller_factory: PortFactory[ControllerOutputPort],
        frame_source_factory: PortFactory[FrameSourcePort],
        resource_store_factory: PortFactory[ResourceStorePort],
        artifact_store_factory: ArtifactStoreFactory,
        notification_factory: PortFactory[NotificationPort],
        logger_factory: PortFactory[LoggerPort],
        preview_frame_source_factory: LifetimePortFactory[FrameSourcePort] | None = None,
        manual_controller_factory: LifetimePortFactory[ControllerOutputPort] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.registry = registry
        self.settings = dict(settings or {})
        self.runtime = runtime or MacroRuntime(registry)
        self._controller_factory = controller_factory
        self._frame_source_factory = frame_source_factory
        self._resource_store_factory = resource_store_factory
        self._artifact_store_factory = artifact_store_factory
        self._notification_factory = notification_factory
        self._logger_factory = logger_factory
        self._preview_frame_source_factory = preview_frame_source_factory
        self._manual_controller_factory = manual_controller_factory
        self._preview_frame_source: FrameSourcePort | None = None
        self._manual_controller: ControllerOutputPort | None = None

    def build(self, request: RuntimeBuildRequest) -> ExecutionContext:
        definition = self.registry.resolve(request.macro_id)
        started_at = datetime.now()
        run_id = uuid4().hex
        run_log_context = RunLogContext(
            run_id=run_id,
            macro_id=definition.id,
            macro_name=definition.display_name,
            entrypoint=request.entrypoint,
            started_at=started_at,
        )
        logger = self._logger_factory(request, definition).bind_context(run_log_context)
        file_args = self.registry.get_settings(definition)
        exec_args = {**file_args, **dict(request.exec_args or {})}
        metadata = dict(request.metadata or {})
        return ExecutionContext(
            run_id=run_id,
            macro_id=definition.id,
            macro_name=definition.display_name,
            run_log_context=run_log_context,
            exec_args=exec_args,
            metadata=metadata,
            cancellation_token=CancellationToken(),
            controller=self._controller_factory(request, definition),
            frame_source=self._frame_source_factory(request, definition),
            resources=self._resource_store_factory(request, definition),
            artifacts=self._artifact_store_factory(request, definition, run_id),
            notifications=self._notification_factory(request, definition),
            logger=logger,
            options=RuntimeOptions(allow_dummy=self._allow_dummy(request)),
        )

    def run(self, request: RuntimeBuildRequest) -> RunResult:
        return self.runtime.run(self.build(request))

    def start(self, request: RuntimeBuildRequest) -> RunHandle:
        return self.runtime.start(self.build(request))

    def frame_source_for_preview(self) -> FrameSourcePort | None:
        if self._preview_frame_source is None and self._preview_frame_source_factory is not None:
            self._preview_frame_source = self._preview_frame_source_factory()
        return self._preview_frame_source

    def controller_output_for_manual_input(self) -> ControllerOutputPort | None:
        if self._manual_controller is None and self._manual_controller_factory is not None:
            self._manual_controller = self._manual_controller_factory()
        return self._manual_controller

    def shutdown(self) -> None:
        errors: list[Exception] = []
        for port in (self._manual_controller, self._preview_frame_source):
            if port is None:
                continue
            try:
                port.close()
            except Exception as exc:
                errors.append(exc)
        self._manual_controller = None
        self._preview_frame_source = None
        if errors:
            raise ExceptionGroup("Runtime builder shutdown failed", errors)

    def _allow_dummy(self, request: RuntimeBuildRequest) -> bool:
        if request.allow_dummy is not None:
            return request.allow_dummy
        return bool(self.settings.get("runtime.allow_dummy", False))


def create_legacy_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    protocol: SerialProtocolInterface,
    notification_handler,
    logger: LoggerPort,
    serial_manager=None,
    capture_manager=None,
    serial_device=None,
    capture_device=None,
    serial_name: str | None = None,
    capture_name: str | None = None,
    baudrate: int | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
) -> MacroRuntimeBuilder:
    """既存具象実装を Port 契約へ接続する Runtime builder。"""
    settings_snapshot = dict(settings or {})
    direct_devices = serial_device is not None or capture_device is not None
    managed_devices = serial_manager is not None or capture_manager is not None
    if direct_devices and managed_devices:
        raise ConfigurationError(
            "direct devices and device managers cannot be mixed",
            component="MacroRuntimeBuilder",
        )
    if direct_devices and (serial_device is None or capture_device is None):
        raise ConfigurationError(
            "serial_device and capture_device must be provided together",
            component="MacroRuntimeBuilder",
        )
    if not direct_devices and (serial_manager is None or capture_manager is None):
        raise ConfigurationError(
            "serial_manager and capture_manager are required",
            component="MacroRuntimeBuilder",
        )

    resolved_serial_name = _optional_name(
        serial_name if serial_name is not None else settings_snapshot.get("serial_device")
    )
    resolved_capture_name = _optional_name(
        capture_name if capture_name is not None else settings_snapshot.get("capture_device")
    )
    resolved_baudrate = _optional_int(
        baudrate if baudrate is not None else settings_snapshot.get("serial_baud")
    )
    lifetime_request = RuntimeBuildRequest(macro_id="__gui_lifetime__")

    return MacroRuntimeBuilder(
        project_root=project_root,
        registry=registry,
        settings=settings_snapshot,
        controller_factory=lambda _request, _definition: SerialControllerOutputPort(
            (
                serial_device
                if direct_devices
                else _resolve_serial_device(
                    serial_manager,
                    resolved_serial_name,
                    resolved_baudrate,
                    detection_timeout_sec,
                    _allow_dummy(settings_snapshot, _request),
                )
            ),
            protocol,
        ),
        frame_source_factory=lambda _request, _definition: CaptureFrameSourcePort(
            capture_device
            if direct_devices
            else _resolve_capture_device(
                capture_manager,
                resolved_capture_name,
                detection_timeout_sec,
                _allow_dummy(settings_snapshot, _request),
            )
        ),
        resource_store_factory=lambda _request, definition: LocalResourceStore(
            MacroResourceScope.from_definition(definition, project_root)
        ),
        artifact_store_factory=lambda _request, definition, run_id: LocalRunArtifactStore(
            Path(project_root) / "runs" / run_id / "outputs",
            macro_id=definition.id,
            run_id=run_id,
        ),
        notification_factory=lambda _request, _definition: (
            NoopNotificationAdapter()
            if notification_handler is None
            else NotificationHandlerAdapter(notification_handler)
        ),
        logger_factory=lambda _request, _definition: logger,
        preview_frame_source_factory=lambda: CaptureFrameSourcePort(
            capture_device
            if direct_devices
            else _resolve_capture_device(
                capture_manager,
                resolved_capture_name,
                detection_timeout_sec,
                _allow_dummy(settings_snapshot, lifetime_request),
            )
        ),
        manual_controller_factory=lambda: SerialControllerOutputPort(
            (
                serial_device
                if direct_devices
                else _resolve_serial_device(
                    serial_manager,
                    resolved_serial_name,
                    resolved_baudrate,
                    detection_timeout_sec,
                    _allow_dummy(settings_snapshot, lifetime_request),
                )
            ),
            protocol,
        ),
    )


def _allow_dummy(settings: dict[str, Any], request: RuntimeBuildRequest) -> bool:
    if request.allow_dummy is not None:
        return request.allow_dummy
    return bool(settings.get("runtime.allow_dummy", False))


def _resolve_serial_device(
    manager,
    name: str | None,
    baudrate: int | None,
    timeout_sec: float,
    allow_dummy: bool,
):
    if name is not None:
        _reject_dummy_name("serial", name, allow_dummy)
        device = _device_map(manager).get(name)
        if _active_device(manager) is not device:
            _ensure_device_registered(manager, name, timeout_sec, "serial")
            device = _device_map(manager).get(name)
        if _active_device(manager) is not device:
            manager.set_active(name, baudrate or 9600)
    device = _active_or_allowed_dummy(manager, "serial", allow_dummy)
    _reject_dummy_device(manager, "serial", device, allow_dummy)
    return device


def _resolve_capture_device(manager, name: str | None, timeout_sec: float, allow_dummy: bool):
    if name is not None:
        _reject_dummy_name("capture", name, allow_dummy)
        device = _device_map(manager).get(name)
        if _active_device(manager) is not device:
            _ensure_device_registered(manager, name, timeout_sec, "capture")
            device = _device_map(manager).get(name)
        if _active_device(manager) is not device:
            manager.set_active(name)
    device = _active_or_allowed_dummy(manager, "capture", allow_dummy)
    _reject_dummy_device(manager, "capture", device, allow_dummy)
    return device


def _active_or_allowed_dummy(manager, device_type: str, allow_dummy: bool):
    active_device = _active_device(manager)
    if active_device is not None:
        return active_device
    if allow_dummy:
        return manager.get_active_device()
    raise ConfigurationError(
        f"{device_type} device is not selected",
        code="NYX_RUNTIME_DEVICE_NOT_SELECTED",
        component="MacroRuntimeBuilder",
        details={"device_type": device_type, "available_devices": _real_device_names(manager)},
    )


def _ensure_device_registered(manager, name: str, timeout_sec: float, device_type: str) -> None:
    auto_register = getattr(manager, "auto_register_devices", None)
    if auto_register is not None:
        auto_register()
    available_devices = _wait_for_device(manager, name, timeout_sec)
    if name not in available_devices:
        raise ConfigurationError(
            f"{device_type} device '{name}' not found",
            code="NYX_RUNTIME_DEVICE_NOT_FOUND",
            component="MacroRuntimeBuilder",
            details={"device_type": device_type, "available_devices": available_devices},
        )


def _wait_for_device(manager, desired_name: str, timeout_sec: float) -> list[str]:
    deadline = time.monotonic() + timeout_sec
    while True:
        devices = list(manager.list_devices())
        if desired_name in devices:
            return devices
        if time.monotonic() >= deadline:
            return devices
        time.sleep(0.05)


def _reject_dummy_name(device_type: str, name: str, allow_dummy: bool) -> None:
    if name == DUMMY_DEVICE_NAME and not allow_dummy:
        raise ConfigurationError(
            f"{device_type} dummy device is not allowed",
            code="NYX_RUNTIME_DUMMY_DEVICE_NOT_ALLOWED",
            component="MacroRuntimeBuilder",
            details={"device_type": device_type},
        )


def _reject_dummy_device(manager, device_type: str, device, allow_dummy: bool) -> None:
    if allow_dummy:
        return
    if _device_map(manager).get(DUMMY_DEVICE_NAME) is device:
        raise ConfigurationError(
            f"{device_type} dummy device is not allowed",
            code="NYX_RUNTIME_DUMMY_DEVICE_NOT_ALLOWED",
            component="MacroRuntimeBuilder",
            details={"device_type": device_type},
        )


def _device_map(manager) -> dict[str, object]:
    devices = getattr(manager, "devices", {})
    return dict(devices)


def _active_device(manager):
    return getattr(manager, "active_device", None)


def _real_device_names(manager) -> list[str]:
    return [name for name in manager.list_devices() if name != DUMMY_DEVICE_NAME]


def _optional_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
