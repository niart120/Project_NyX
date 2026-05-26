from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.io.ports import (
    ControllerOutputPort,
    FrameNotReadyError,
    FrameSourcePort,
    NotificationPort,
)
from nyxpy.framework.core.io.resources import (
    ArtifactScope,
    DefaultResourcePathGuard,
    MacroResourceScope,
    OverwritePolicy,
    ResourceKind,
    ResourceNotFoundError,
    ResourceRef,
    ResourceSource,
    ResourceStorePort,
    RunArtifactStore,
)
from nyxpy.framework.core.logger.ports import (
    LogEvent,
    LogExtraValue,
    LoggerPort,
    LogLevel,
    RunLogContext,
    TechnicalLog,
    UserEvent,
)


class FakeControllerOutputPort(ControllerOutputPort):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.closed = False

    def press(self, keys: tuple[KeyType, ...]) -> None:
        self.events.append(("press", keys))

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        self.events.append(("hold", keys))

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        self.events.append(("release", keys))

    def keyboard(self, text: str) -> None:
        self.events.append(("keyboard", text))

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        self.events.append(("type_key", key))

    def close(self) -> None:
        self.closed = True
        self.events.append(("close", None))


class FakeFullCapabilityController(FakeControllerOutputPort):
    @property
    def supports_touch(self) -> bool:
        return True

    def touch_down(self, x: int, y: int) -> None:
        self.events.append(("touch_down", (x, y)))

    def touch_up(self) -> None:
        self.events.append(("touch_up", None))

    def disable_sleep(self, enabled: bool = True) -> None:
        self.events.append(("disable_sleep", enabled))


class FakeFrameSourcePort(FrameSourcePort):
    def __init__(self, frame: cv2.typing.MatLike | None = None) -> None:
        self.frame = frame if frame is not None else np.zeros((2, 2, 3), dtype=np.uint8)
        self.initialized = False
        self.closed = False
        self.frame_lock = Lock()

    def initialize(self) -> None:
        self.initialized = True

    def await_ready(self, timeout: float) -> bool:
        if timeout is None or timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        return self.initialized

    def latest_frame(self) -> cv2.typing.MatLike:
        if not self.initialized:
            raise FrameNotReadyError()
        with self.frame_lock:
            return self.frame.copy()

    def try_latest_frame(self) -> cv2.typing.MatLike | None:
        if not self.initialized:
            return None
        if not self.frame_lock.acquire(blocking=False):
            return None
        try:
            return self.frame.copy()
        finally:
            self.frame_lock.release()

    def close(self) -> None:
        self.closed = True


class FakeNotificationPort(NotificationPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, cv2.typing.MatLike | None]] = []

    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        self.calls.append((text, img))


class FakeResourceStore(ResourceStorePort):
    def __init__(self, scope: MacroResourceScope) -> None:
        self.scope = scope
        self.guard = DefaultResourcePathGuard()
        self.images: dict[Path, cv2.typing.MatLike] = {}
        self.blobs: dict[Path, bytes] = {}

    def resolve_asset_path(self, name: str | Path) -> ResourceRef:
        for index, root in enumerate(self.scope.assets_roots):
            candidate = self.guard.resolve_under_root(root, name)
            if candidate in self.images or candidate in self.blobs or candidate.exists():
                return ResourceRef(
                    kind=ResourceKind.ASSET,
                    source=(
                        ResourceSource.STANDARD_ASSETS
                        if index == 0
                        else ResourceSource.MACRO_PACKAGE
                    ),
                    path=candidate,
                    relative_path=candidate.relative_to(root.resolve(strict=False)),
                    macro_id=self.scope.macro_id,
                )
        raise ResourceNotFoundError(f"resource not found: {name}")

    def load_image(self, name: str | Path, grayscale: bool = False) -> cv2.typing.MatLike:
        ref = self.resolve_asset_path(name)
        image = self.images.get(ref.path)
        if image is None:
            flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
            image = cv2.imread(str(ref.path), flag)
        if image is None:
            raise ResourceNotFoundError(f"resource not found: {name}")
        if grayscale and len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image.copy()

    def load_blob(self, name: str | Path) -> bytes:
        ref = self.resolve_asset_path(name)
        blob = self.blobs.get(ref.path)
        if blob is not None:
            return blob
        try:
            return ref.path.read_bytes()
        except OSError as exc:
            raise ResourceNotFoundError(f"resource not found: {name}") from exc


class FakeRunArtifactStore(RunArtifactStore):
    def __init__(
        self,
        artifacts_root: Path,
        *,
        macro_id: str,
        run_id: str,
        artifact_dir_name: str = "20260526T235245_run1",
        tracked_limit: int = 65535,
    ) -> None:
        self.artifacts_root = artifacts_root
        self.macro_id = macro_id
        self.run_id = run_id
        self._artifact_dir_name = artifact_dir_name
        self.tracked_limit = tracked_limit
        self.guard = DefaultResourcePathGuard()
        self.saved_images: dict[Path, cv2.typing.MatLike] = {}
        self.saved_blobs: dict[Path, bytes] = {}
        self._tracked_refs: list[ResourceRef] = []
        self._overflow_count = 0

    @property
    def artifact_dir_name(self) -> str:
        return self._artifact_dir_name

    @property
    def artifacts_overflow_count(self) -> int:
        return self._overflow_count

    def snapshot(self) -> tuple[ResourceRef, ...]:
        return tuple(self._tracked_refs)

    def resolve_artifact_path(
        self, name: str | Path, *, scope: ArtifactScope = ArtifactScope.RUN
    ) -> ResourceRef:
        root = self._scope_root(scope)
        path = self.guard.resolve_under_root(root, name)
        return ResourceRef(
            kind=ResourceKind.ARTIFACT,
            source=(
                ResourceSource.ARTIFACT_RUN
                if scope is ArtifactScope.RUN
                else ResourceSource.ARTIFACT_STABLE
            ),
            path=path,
            relative_path=path.relative_to(self.artifacts_root.resolve(strict=False)),
            macro_id=self.macro_id,
            run_id=self.run_id,
        )

    def resolve_output_path(self, name: str | Path) -> ResourceRef:
        return self.resolve_artifact_path(name)

    def save_image(
        self,
        name: str | Path,
        image: cv2.typing.MatLike,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        ref = self.resolve_artifact_path(name, scope=scope)
        self.saved_images[ref.path] = image.copy()
        self._record(ref)
        return ref

    def save_blob(
        self,
        name: str | Path,
        data: bytes,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        overwrite: OverwritePolicy | None = None,
        atomic: bool | None = None,
    ) -> ResourceRef:
        ref = self.resolve_artifact_path(name, scope=scope)
        self.saved_blobs[ref.path] = bytes(data)
        self._record(ref)
        return ref

    def load_image(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
        grayscale: bool = False,
    ) -> cv2.typing.MatLike:
        ref = (
            artifact
            if isinstance(artifact, ResourceRef)
            else self.resolve_artifact_path(artifact, scope=scope)
        )
        image = self.saved_images[ref.path]
        if grayscale and len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image.copy()

    def load_blob(
        self,
        artifact: ResourceRef | str | Path,
        *,
        scope: ArtifactScope = ArtifactScope.RUN,
    ) -> bytes:
        ref = (
            artifact
            if isinstance(artifact, ResourceRef)
            else self.resolve_artifact_path(artifact, scope=scope)
        )
        return self.saved_blobs[ref.path]

    def _scope_root(self, scope: ArtifactScope) -> Path:
        if scope is ArtifactScope.RUN:
            return self.artifacts_root / self._artifact_dir_name
        return self.artifacts_root / "stable"

    def _record(self, ref: ResourceRef) -> None:
        self._tracked_refs = [saved for saved in self._tracked_refs if saved.path != ref.path]
        self._tracked_refs.append(ref)
        while len(self._tracked_refs) > self.tracked_limit:
            self._tracked_refs.pop(0)
            self._overflow_count += 1


class FakeLoggerPort(LoggerPort):
    def __init__(
        self,
        *,
        context: RunLogContext | None = None,
        technical_logs: list[TechnicalLog] | None = None,
        user_events: list[UserEvent] | None = None,
    ) -> None:
        self.context = context
        self.technical_logs = technical_logs if technical_logs is not None else []
        self.user_events = user_events if user_events is not None else []

    def bind_context(self, context: RunLogContext) -> FakeLoggerPort:
        return FakeLoggerPort(
            context=context,
            technical_logs=self.technical_logs,
            user_events=self.user_events,
        )

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
        log_event = self._event(
            level=level,
            message=message,
            component=component,
            event=event,
            extra=extra,
            exception_type=type(exc).__name__ if exc is not None else None,
        )
        self.technical_logs.append(TechnicalLog(log_event))

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
        log_event = self._event(
            level=level,
            message=message,
            component=component,
            event=event,
            extra=extra,
        )
        self.user_events.append(
            UserEvent(
                timestamp=log_event.timestamp,
                level=log_event.level,
                component=log_event.component,
                event=log_event.event,
                message=log_event.message,
                run_id=log_event.run_id,
                macro_id=log_event.macro_id,
                code=code,
                extra=dict(log_event.extra),
            )
        )

    def _event(
        self,
        *,
        level: str,
        message: str,
        component: str,
        event: str,
        extra: dict[str, LogExtraValue] | None,
        exception_type: str | None = None,
    ) -> LogEvent:
        log_level = LogLevel(level)
        return LogEvent(
            timestamp=datetime.now(),
            level=log_level,
            component=component,
            event=event,
            message=message,
            run_id=self.context.run_id if self.context else None,
            macro_id=self.context.macro_id if self.context else None,
            extra=dict(extra or {}),
            exception_type=exception_type,
        )
