from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nyxpy.framework.core.logger.ports import LoggerPort
from nyxpy.framework.core.utils.cancellation import CancellationToken


@dataclass(frozen=True)
class RuntimeOptions:
    allow_dummy: bool = False
    device_detection_timeout_sec: float = 5.0
    frame_ready_timeout_sec: float = 3.0
    release_timeout_sec: float = 2.0


@dataclass(frozen=True)
class RunContext:
    run_id: str
    macro_id: str
    macro_name: str
    started_at: datetime
    cancellation_token: CancellationToken
    logger: LoggerPort | None = None
