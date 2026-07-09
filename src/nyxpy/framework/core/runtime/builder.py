"""Macro runtime の構築 helper。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nyxpy.framework.core.hardware.capture_source import capture_source_from_settings
from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig
from nyxpy.framework.core.hardware.swbt.factory import SwbtControllerOutputPortFactory
from nyxpy.framework.core.io.adapters import (
    NoopNotificationAdapter,
    NotificationHandlerAdapter,
)
from nyxpy.framework.core.io.controller_config import ControllerConfig, SerialControllerConfig
from nyxpy.framework.core.io.device_factories import (
    FrameSourcePortFactory,
    SerialControllerOutputPortFactory,
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
    OverwritePolicy,
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
from nyxpy.framework.core.settings.schema import dotted_get
from nyxpy.framework.core.utils.cancellation import CancellationToken

type PortFactory[T] = Callable[[RuntimeBuildRequest, MacroDefinition], T]
type LifetimePortFactory[T] = Callable[[], T]
type ArtifactStoreFactory = Callable[
    [RuntimeBuildRequest, MacroDefinition, str, str], RunArtifactStore
]
type ShutdownCallback = Callable[[], None]


class MacroRuntimeBuilder:
    """MacroDefinition から実行 context と runtime handle を組み立てます。"""

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
        controller_shutdown_callbacks: tuple[ShutdownCallback, ...] = (),
        frame_source_shutdown_callbacks: tuple[ShutdownCallback, ...] = (),
        shutdown_callbacks: tuple[ShutdownCallback, ...] = (),
    ) -> None:
        """Registry、各 port factory、settings snapshot、runtime を保持します。"""
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
        self._controller_shutdown_callbacks = controller_shutdown_callbacks
        self._frame_source_shutdown_callbacks = frame_source_shutdown_callbacks
        self._shutdown_callbacks = shutdown_callbacks
        self._preview_frame_source: FrameSourcePort | None = None
        self._manual_controller: ControllerOutputPort | None = None

    def build(self, request: RuntimeBuildRequest) -> ExecutionContext:
        definition = self.registry.resolve(request.macro_id)
        started_at = datetime.now()
        run_id = uuid4().hex
        artifact_dir_name = _artifact_dir_name(started_at, run_id, self.settings)
        file_args = self.registry.get_settings(definition)
        exec_args = {**file_args, **dict(request.exec_args or {})}
        run_log_context = RunLogContext(
            run_id=run_id,
            macro_id=definition.id,
            macro_name=definition.display_name,
            entrypoint=request.entrypoint,
            started_at=started_at,
        )
        logger = self._logger_factory(request, definition).bind_context(run_log_context)
        metadata = dict(request.metadata or {})
        return ExecutionContext(
            run_id=run_id,
            macro_id=definition.id,
            macro_name=definition.display_name,
            artifact_dir_name=artifact_dir_name,
            run_log_context=run_log_context,
            exec_args=exec_args,
            metadata=metadata,
            cancellation_token=CancellationToken(),
            controller=self._controller_factory(request, definition),
            frame_source=self._frame_source_factory(request, definition),
            resources=self._resource_store_factory(request, definition),
            artifacts=self._artifact_store_factory(request, definition, run_id, artifact_dir_name),
            notifications=self._notification_factory(request, definition),
            logger=logger,
            options=RuntimeOptions(
                allow_dummy=self._allow_dummy(request),
                command_debug_enabled=_command_debug_enabled(self.settings, exec_args, metadata),
            ),
        )

    def run(self, request: RuntimeBuildRequest) -> RunResult:
        return self.runtime.run(self.build(request))

    def start(self, request: RuntimeBuildRequest) -> RunHandle:
        return self.runtime.start(self.build(request))

    def frame_source_for_preview(self) -> FrameSourcePort | None:
        if self._preview_frame_source is None and self._preview_frame_source_factory is not None:
            frame_source = self._preview_frame_source_factory()
            try:
                frame_source.initialize()
            except Exception:
                frame_source.close()
                raise
            self._preview_frame_source = frame_source
        return self._preview_frame_source

    def controller_output_for_manual_input(self) -> ControllerOutputPort | None:
        if self._manual_controller is None and self._manual_controller_factory is not None:
            self._manual_controller = self._manual_controller_factory()
        return self._manual_controller

    def detach_preview_frame_source(self) -> FrameSourcePort | None:
        """GUI lifetime preview port を builder shutdown 対象から外す。"""
        port = self._preview_frame_source
        self._preview_frame_source = None
        self._frame_source_shutdown_callbacks = ()
        return port

    def attach_preview_frame_source(self, port: FrameSourcePort | None) -> None:
        """既存 GUI lifetime preview port をこの builder の管理下へ移す。"""
        self._preview_frame_source = port

    def detach_frame_source_shutdown_callbacks(self) -> tuple[ShutdownCallback, ...]:
        """Preview port が依存する shutdown callback を builder shutdown 対象から外す。"""
        callbacks = self._frame_source_shutdown_callbacks
        self._frame_source_shutdown_callbacks = ()
        return callbacks

    def extend_frame_source_shutdown_callbacks(
        self,
        callbacks: tuple[ShutdownCallback, ...],
    ) -> None:
        """移管された preview port 用の shutdown callback を追加する。"""
        self._frame_source_shutdown_callbacks += callbacks

    def detach_manual_controller(self) -> ControllerOutputPort | None:
        """GUI lifetime manual controller port を builder shutdown 対象から外す。"""
        port = self._manual_controller
        self._manual_controller = None
        self._controller_shutdown_callbacks = ()
        return port

    def attach_manual_controller(self, port: ControllerOutputPort | None) -> None:
        """既存 GUI lifetime manual controller port をこの builder の管理下へ移す。"""
        self._manual_controller = port

    def detach_controller_shutdown_callbacks(self) -> tuple[ShutdownCallback, ...]:
        """Manual controller port が依存する shutdown callback を builder shutdown 対象から外す。"""
        callbacks = self._controller_shutdown_callbacks
        self._controller_shutdown_callbacks = ()
        return callbacks

    def extend_controller_shutdown_callbacks(
        self,
        callbacks: tuple[ShutdownCallback, ...],
    ) -> None:
        """移管された manual controller 用の shutdown callback を追加する。"""
        self._controller_shutdown_callbacks += callbacks

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
        for callback in self._controller_shutdown_callbacks:
            try:
                callback()
            except Exception as exc:
                errors.append(exc)
        self._controller_shutdown_callbacks = ()
        for callback in self._frame_source_shutdown_callbacks:
            try:
                callback()
            except Exception as exc:
                errors.append(exc)
        self._frame_source_shutdown_callbacks = ()
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as exc:
                errors.append(exc)
        self._shutdown_callbacks = ()
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
    controller_config: ControllerConfig,
    notification_handler,
    logger: LoggerPort,
    device_discovery: DeviceDiscoveryService | None = None,
    serial_controller_factory: SerialControllerOutputPortFactory | None = None,
    swbt_controller_factory: SwbtControllerOutputPortFactory | None = None,
    frame_source_factory: FrameSourcePortFactory | None = None,
    capture_name: str | None = None,
    detection_timeout_sec: float = 2.0,
    settings: SettingsSnapshot | None = None,
    lifetime_allow_dummy: bool | None = None,
) -> MacroRuntimeBuilder:
    """Device discovery と Port factory を Runtime builder へ接続する。"""
    settings_snapshot = dict(settings or {})
    resolved_capture_name = _optional_name(capture_name)
    capture_source_type = str(settings_snapshot.get("capture_source_type", "camera") or "camera")
    capture_source = capture_source_from_settings(
        settings_snapshot,
        capture_name_override=resolved_capture_name if capture_source_type == "camera" else None,
    )
    lifetime_request = RuntimeBuildRequest(macro_id="__gui_lifetime__")
    discovery = device_discovery or DeviceDiscoveryService(logger=logger)
    discovery.detect(detection_timeout_sec)
    serial_factory = serial_controller_factory
    swbt_factory = swbt_controller_factory
    if isinstance(controller_config, SerialControllerConfig) and serial_factory is None:
        serial_factory = SerialControllerOutputPortFactory(
            discovery=discovery,
            protocol=ProtocolFactory.create_protocol(controller_config.protocol),
        )
    if isinstance(controller_config, SwbtControllerConfig) and swbt_factory is None:
        swbt_factory = SwbtControllerOutputPortFactory()
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

    controller_port_factory = make_controller_port_factory(
        config=controller_config,
        serial_factory=serial_factory,
        swbt_factory=swbt_factory,
        allow_dummy=allow_dummy,
        detection_timeout_sec=detection_timeout_sec,
    )
    controller_shutdown_callbacks = _controller_shutdown_callbacks(
        config=controller_config,
        serial_factory=serial_factory,
        swbt_factory=swbt_factory,
    )
    frame_source_shutdown_callbacks = (frame_factory.close,)

    return MacroRuntimeBuilder(
        project_root=project_root,
        registry=registry,
        settings=settings_snapshot,
        controller_factory=controller_port_factory,
        frame_source_factory=lambda request, _definition: frame_factory.create(
            source=capture_source,
            allow_dummy=allow_dummy(request),
            timeout_sec=detection_timeout_sec,
        ),
        resource_store_factory=lambda _request, definition: LocalResourceStore(
            MacroResourceScope.from_definition(definition, project_root)
        ),
        artifact_store_factory=lambda _request, definition, run_id, artifact_dir_name: (
            LocalRunArtifactStore(
                MacroResourceScope.from_definition(definition, project_root).artifacts_root,
                macro_id=definition.id,
                run_id=run_id,
                artifact_dir_name=artifact_dir_name,
                tracked_limit=_resource_tracked_artifact_limit(settings_snapshot),
                overwrite=_resource_overwrite_policy(settings_snapshot),
                atomic=_resource_atomic_write(settings_snapshot),
            )
        ),
        notification_factory=lambda _request, _definition: (
            NoopNotificationAdapter()
            if notification_handler is None
            else NotificationHandlerAdapter(notification_handler)
        ),
        logger_factory=lambda _request, _definition: logger,
        preview_frame_source_factory=lambda: frame_factory.create(
            source=capture_source,
            allow_dummy=lifetime_dummy(),
            timeout_sec=detection_timeout_sec,
        ),
        manual_controller_factory=lambda: _create_controller_port(
            config=controller_config,
            serial_factory=serial_factory,
            swbt_factory=swbt_factory,
            allow_dummy=lifetime_dummy(),
            detection_timeout_sec=detection_timeout_sec,
        ),
        controller_shutdown_callbacks=controller_shutdown_callbacks,
        frame_source_shutdown_callbacks=frame_source_shutdown_callbacks,
    )


def make_controller_port_factory(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory | None,
    swbt_factory: SwbtControllerOutputPortFactory | None,
    allow_dummy: Callable[[RuntimeBuildRequest], bool],
    detection_timeout_sec: float,
) -> PortFactory[ControllerOutputPort]:
    """ControllerConfig に対応する runtime controller port factory を作る。"""

    def create(request: RuntimeBuildRequest, _definition: MacroDefinition) -> ControllerOutputPort:
        return _create_controller_port(
            config=config,
            serial_factory=serial_factory,
            swbt_factory=swbt_factory,
            allow_dummy=allow_dummy(request),
            detection_timeout_sec=detection_timeout_sec,
        )

    return create


def _create_controller_port(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory | None,
    swbt_factory: SwbtControllerOutputPortFactory | None,
    allow_dummy: bool,
    detection_timeout_sec: float,
) -> ControllerOutputPort:
    if isinstance(config, SerialControllerConfig):
        if serial_factory is None:
            raise RuntimeError("serial controller factory is not configured")
        return serial_factory.create(
            name=config.device,
            baudrate=config.baudrate,
            allow_dummy=allow_dummy,
            timeout_sec=detection_timeout_sec,
        )
    if isinstance(config, SwbtControllerConfig):
        if swbt_factory is None:
            raise RuntimeError("swbt controller factory is not configured")
        return swbt_factory.create(
            config=config,
            allow_dummy=allow_dummy,
            timeout_sec=config.connect_timeout_sec,
        )
    raise TypeError(f"unsupported controller config: {type(config).__name__}")


def _controller_shutdown_callbacks(
    *,
    config: ControllerConfig,
    serial_factory: SerialControllerOutputPortFactory | None,
    swbt_factory: SwbtControllerOutputPortFactory | None,
) -> tuple[ShutdownCallback, ...]:
    if isinstance(config, SerialControllerConfig):
        return () if serial_factory is None else (serial_factory.close,)
    if isinstance(config, SwbtControllerConfig):
        return () if swbt_factory is None else (swbt_factory.close,)
    return ()


def _allow_dummy(settings: dict[str, Any], request: RuntimeBuildRequest) -> bool:
    if request.allow_dummy is not None:
        return request.allow_dummy
    return bool(settings.get("runtime.allow_dummy", False))


def _artifact_dir_name(started_at: datetime, run_id: str, settings: Mapping[str, Any]) -> str:
    timestamp_format = str(settings.get("resource.artifact_timestamp_format", "%Y%m%dT%H%M%S"))
    name_format = str(settings.get("resource.artifact_dir_name_format", "{timestamp}_{short_id}"))
    short_id_length = int(settings.get("resource.short_id_length", 4))
    if short_id_length <= 0:
        raise ValueError("resource.short_id_length must be greater than 0")
    timestamp = started_at.strftime(timestamp_format)
    short_id = run_id[:short_id_length]
    return name_format.format(timestamp=timestamp, short_id=short_id, run_id=run_id)


def _resource_tracked_artifact_limit(settings: Mapping[str, Any]) -> int:
    return int(settings.get("resource.tracked_artifact_limit", 65535))


def _resource_overwrite_policy(settings: Mapping[str, Any]) -> OverwritePolicy:
    value = settings.get("resource.overwrite_policy", OverwritePolicy.REPLACE)
    return value if isinstance(value, OverwritePolicy) else OverwritePolicy(str(value))


def _resource_atomic_write(settings: Mapping[str, Any]) -> bool:
    return bool(settings.get("resource.atomic_write", True))


def _command_debug_enabled(
    settings: Mapping[str, Any],
    exec_args: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> bool:
    value = dotted_get(
        metadata,
        "logging.command_debug_enabled",
        dotted_get(
            exec_args,
            "logging.command_debug_enabled",
            dotted_get(settings, "logging.command_debug_enabled", False),
        ),
    )
    return bool(value)


def _optional_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value).strip())
