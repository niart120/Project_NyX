from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from nyxpy.framework.core.macro.exceptions import ErrorInfo


class RunStatus(StrEnum):
    SUCCESS = "success"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CleanupWarning(Exception):
    port_name: str
    exception_type: str
    message: str

    def __init__(self, port_name: str, exception_type: str, message: str) -> None:
        super().__init__(message)
        self.port_name = port_name
        self.exception_type = exception_type
        self.message = message


@dataclass(frozen=True)
class RunResult:
    run_id: str
    macro_id: str
    macro_name: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    error: ErrorInfo | None = None
    cleanup_warnings: tuple[CleanupWarning, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.SUCCESS and self.error is None

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()
