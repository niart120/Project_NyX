from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from nyxpy.framework.core.io.ports import ControllerOutputPort, FrameSourcePort, NotificationPort
from nyxpy.framework.core.io.resources import ResourceStorePort, RunArtifactStore
from nyxpy.framework.core.logger.ports import LoggerPort, RunLogContext
from nyxpy.framework.core.macro.exceptions import FrameworkValue
from nyxpy.framework.core.utils.cancellation import CancellationToken

type RuntimeValue = FrameworkValue
type SettingsSnapshot = Mapping[str, FrameworkValue]


@dataclass(frozen=True)
class RuntimeOptions:
    allow_dummy: bool = False
    device_detection_timeout_sec: float = 5.0
    frame_ready_timeout_sec: float = 3.0
    release_timeout_sec: float = 2.0


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    macro_id: str
    macro_name: str
    run_log_context: RunLogContext
    exec_args: Mapping[str, RuntimeValue]
    metadata: Mapping[str, RuntimeValue]
    cancellation_token: CancellationToken
    controller: ControllerOutputPort
    frame_source: FrameSourcePort
    resources: ResourceStorePort
    artifacts: RunArtifactStore
    notifications: NotificationPort
    logger: LoggerPort
    options: RuntimeOptions = RuntimeOptions()

    def __post_init__(self) -> None:
        object.__setattr__(self, "exec_args", MappingProxyType(dict(self.exec_args)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class RunContext:
    run_id: str
    macro_id: str
    macro_name: str
    started_at: datetime
    cancellation_token: CancellationToken
    logger: LoggerPort | None = None


@dataclass(frozen=True)
class RuntimeBuildRequest:
    macro_id: str
    entrypoint: str = "runtime"
    exec_args: Mapping[str, RuntimeValue] | None = None
    allow_dummy: bool | None = None
    metadata: Mapping[str, RuntimeValue] | None = None
