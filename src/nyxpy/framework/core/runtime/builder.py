from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import cv2

from nyxpy.framework.core.constants import KeyboardOp, KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.io.ports import (
    ControllerOutputPort,
    FrameNotReadyError,
    FrameSourcePort,
    NotificationPort,
)
from nyxpy.framework.core.io.resources import (
    DefaultResourcePathGuard,
    OverwritePolicy,
    ResourceKind,
    ResourceNotFoundError,
    ResourceRef,
    ResourceSource,
    ResourceStorePort,
    RunArtifactStore,
)
from nyxpy.framework.core.logger.ports import (
    LogExtraValue,
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
from nyxpy.framework.core.utils.helper import validate_keyboard_text

type PortFactory[T] = Callable[[RuntimeBuildRequest, MacroDefinition], T]


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
        artifact_store_factory: PortFactory[RunArtifactStore],
        notification_factory: PortFactory[NotificationPort],
        logger_factory: PortFactory[LoggerPort],
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
            artifacts=self._artifact_store_factory(request, definition),
            notifications=self._notification_factory(request, definition),
            logger=logger,
            options=RuntimeOptions(allow_dummy=self._allow_dummy(request)),
        )

    def run(self, request: RuntimeBuildRequest) -> RunResult:
        return self.runtime.run(self.build(request))

    def start(self, request: RuntimeBuildRequest) -> RunHandle:
        return self.runtime.start(self.build(request))

    def _allow_dummy(self, request: RuntimeBuildRequest) -> bool:
        if request.allow_dummy is not None:
            return request.allow_dummy
        return bool(self.settings.get("runtime.allow_dummy", False))


def create_legacy_runtime_builder(
    *,
    project_root: Path,
    registry: MacroRegistry,
    serial_device,
    capture_device,
    resource_io: StaticResourceIO,
    protocol: SerialProtocolInterface,
    notification_handler,
    log_manager,
) -> MacroRuntimeBuilder:
    """Phase 8 まで既存具象実装を Port 契約へ閉じ込める最小 adapter。"""

    return MacroRuntimeBuilder(
        project_root=project_root,
        registry=registry,
        controller_factory=lambda _request, _definition: _LegacyControllerOutputPort(
            serial_device, protocol
        ),
        frame_source_factory=lambda _request, _definition: _LegacyFrameSourcePort(capture_device),
        resource_store_factory=lambda _request, definition: _LegacyResourceStore(
            resource_io, definition
        ),
        artifact_store_factory=lambda _request, definition: _LegacyRunArtifactStore(
            resource_io, definition
        ),
        notification_factory=lambda _request, _definition: _LegacyNotificationPort(
            notification_handler
        ),
        logger_factory=lambda _request, _definition: _LegacyLoggerPort(log_manager),
    )


class _LegacyControllerOutputPort(ControllerOutputPort):
    def __init__(self, serial_device, protocol: SerialProtocolInterface) -> None:
        self.serial_device = serial_device
        self.protocol = protocol

    def press(self, keys: tuple[KeyType, ...]) -> None:
        self.serial_device.send(self.protocol.build_press_command(keys))

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        self.serial_device.send(self.protocol.build_hold_command(keys))

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        self.serial_device.send(self.protocol.build_release_command(keys))

    def keyboard(self, text: str) -> None:
        text = validate_keyboard_text(text)
        try:
            self.serial_device.send(self.protocol.build_keyboard_command(text))
        except (ValueError, NotImplementedError):
            for char in text:
                self.type_key(KeyCode(char))
        try:
            self.serial_device.send(
                self.protocol.build_keytype_command(KeyCode(""), KeyboardOp.ALL_RELEASE)
            )
        except NotImplementedError:
            pass

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        match key:
            case KeyCode():
                press_op = KeyboardOp.PRESS
                release_op = KeyboardOp.RELEASE
            case SpecialKeyCode():
                press_op = KeyboardOp.SPECIAL_PRESS
                release_op = KeyboardOp.SPECIAL_RELEASE
            case _:
                raise ValueError(f"Invalid key type: {type(key)}")
        self.serial_device.send(self.protocol.build_keytype_command(key, press_op))
        self.serial_device.send(self.protocol.build_keytype_command(key, release_op))

    def close(self) -> None:
        pass


class _LegacyFrameSourcePort(FrameSourcePort):
    def __init__(self, capture_device) -> None:
        self.capture_device = capture_device

    def initialize(self) -> None:
        initialize = getattr(self.capture_device, "initialize", None)
        if initialize is not None:
            initialize()

    def await_ready(self, timeout: float) -> bool:
        if timeout is None or timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        deadline = time.monotonic() + timeout
        while True:
            if self.capture_device.get_frame() is not None:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def latest_frame(self) -> cv2.typing.MatLike:
        frame = self.capture_device.get_frame()
        if frame is None:
            raise FrameNotReadyError()
        return frame.copy()

    def close(self) -> None:
        pass


class _LegacyResourceStore(ResourceStorePort):
    def __init__(self, resource_io: StaticResourceIO, definition: MacroDefinition) -> None:
        self.resource_io = resource_io
        self.definition = definition

    def resolve_asset_path(self, name: str | Path) -> ResourceRef:
        path = Path(self.resource_io.root_dir_path) / name
        if not path.exists():
            raise ResourceNotFoundError(f"resource not found: {name}")
        return ResourceRef(
            kind=ResourceKind.ASSET,
            source=ResourceSource.STANDARD_ASSETS,
            path=path,
            relative_path=Path(name),
            macro_id=self.definition.id,
        )

    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike:
        return self.resource_io.load_image(name, grayscale=grayscale)


class _LegacyRunArtifactStore(RunArtifactStore):
    def __init__(self, resource_io: StaticResourceIO, definition: MacroDefinition) -> None:
        self.resource_io = resource_io
        self.definition = definition
        self.guard = DefaultResourcePathGuard()

    def resolve_output_path(self, name: str | Path) -> ResourceRef:
        path = self.guard.resolve_under_root(Path(self.resource_io.root_dir_path), name)
        return ResourceRef(
            kind=ResourceKind.OUTPUT,
            source=ResourceSource.RUN_OUTPUTS,
            path=path,
            relative_path=Path(name),
            macro_id=self.definition.id,
        )

    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        overwrite: OverwritePolicy = OverwritePolicy.REPLACE,
        atomic: bool = True,
    ) -> ResourceRef:
        self.resource_io.save_image(name, image)
        return self.resolve_output_path(name)

    def open_output(
        self,
        name: str | Path,
        mode: str = "xb",
        *,
        overwrite: OverwritePolicy = OverwritePolicy.ERROR,
        atomic: bool = True,
    ) -> BinaryIO:
        ref = self.resolve_output_path(name)
        ref.path.parent.mkdir(parents=True, exist_ok=True)
        return ref.path.open(mode)


class _LegacyNotificationPort(NotificationPort):
    def __init__(self, notification_handler) -> None:
        self.notification_handler = notification_handler

    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        if self.notification_handler is not None:
            self.notification_handler.publish(text, img)


class _LegacyLoggerPort(LoggerPort):
    def __init__(self, log_manager, context: RunLogContext | None = None) -> None:
        self.log_manager = log_manager
        self.context = context

    def bind_context(self, context: RunLogContext) -> _LegacyLoggerPort:
        return _LegacyLoggerPort(self.log_manager, context)

    def technical(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str = "log.message",
        extra: dict[str, LogExtraValue] | None = None,
        exc: BaseException | None = None,
    ) -> None:
        self.log_manager.log(level, message, component=component)

    def user(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str,
        code: str | None = None,
        extra: dict[str, LogExtraValue] | None = None,
    ) -> None:
        self.log_manager.log(level, message, component=component)
