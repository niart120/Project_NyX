from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.io.adapters import (
    NoopNotificationAdapter,
    NotificationHandlerAdapter,
)
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
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
type ShutdownCallback = Callable[[], None]


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
        shutdown_callbacks: tuple[ShutdownCallback, ...] = (),
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
        self._shutdown_callbacks = shutdown_callbacks
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
            self._preview_frame_source.initialize()
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
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("Runtime builder shutdown failed", errors)

    def _allow_dummy(self, request: RuntimeBuildRequest) -> bool:
        if request.allow_dummy is not None:
            return request.allow_dummy
        return bool(self.settings.get("runtime.allow_dummy", False))


def create_device_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    protocol: SerialProtocolInterface,
    notification_handler,
    logger: LoggerPort,
    device_discovery: DeviceDiscoveryService | None = None,
    controller_output_factory: ControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
    serial_name: str | None = None,
    capture_name: str | None = None,
    baudrate: int | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
    lifetime_allow_dummy: bool | None = None,
) -> MacroRuntimeBuilder:
    """Device discovery と Port factory を Runtime builder へ接続する。"""
    settings_snapshot = dict(settings or {})
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
    discovery = device_discovery or DeviceDiscoveryService(logger=logger)
    controller_factory = controller_output_factory or ControllerOutputPortFactory(
        discovery=discovery,
        protocol=protocol,
    )
    frame_factory = frame_source_factory or FrameSourcePortFactory(
        discovery=discovery,
        logger=logger,
    )

    def allow_dummy(request: RuntimeBuildRequest) -> bool:
        return _allow_dummy(settings_snapshot, request)

    def lifetime_dummy() -> bool:
        if lifetime_allow_dummy is not None:
            return lifetime_allow_dummy
        return allow_dummy(lifetime_request)

    return MacroRuntimeBuilder(
        project_root=project_root,
        registry=registry,
        settings=settings_snapshot,
        controller_factory=lambda request, _definition: controller_factory.create(
            name=resolved_serial_name,
            baudrate=resolved_baudrate,
            allow_dummy=allow_dummy(request),
            timeout_sec=detection_timeout_sec,
        ),
        frame_source_factory=lambda request, _definition: frame_factory.create(
            name=resolved_capture_name,
            allow_dummy=allow_dummy(request),
            timeout_sec=detection_timeout_sec,
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
        preview_frame_source_factory=lambda: frame_factory.create(
            name=resolved_capture_name,
            allow_dummy=lifetime_dummy(),
            timeout_sec=detection_timeout_sec,
        ),
        manual_controller_factory=lambda: controller_factory.create(
            name=resolved_serial_name,
            baudrate=resolved_baudrate,
            allow_dummy=lifetime_dummy(),
            timeout_sec=detection_timeout_sec,
        ),
        shutdown_callbacks=(controller_factory.close, frame_factory.close),
    )


def _allow_dummy(settings: dict[str, Any], request: RuntimeBuildRequest) -> bool:
    if request.allow_dummy is not None:
        return request.allow_dummy
    return bool(settings.get("runtime.allow_dummy", False))


def _optional_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
