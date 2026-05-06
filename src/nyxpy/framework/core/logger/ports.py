from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from nyxpy.framework.core.macro.exceptions import FrameworkValue

type LogExtraValue = FrameworkValue


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RunLogContext:
    run_id: str
    macro_id: str
    macro_name: str = ""
    entrypoint: str = "runtime"
    started_at: datetime | None = None


@dataclass(frozen=True)
class LogEvent:
    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    run_id: str | None = None
    macro_id: str | None = None
    extra: dict[str, LogExtraValue] = field(default_factory=dict)
    exception_type: str | None = None
    traceback: str | None = None


@dataclass(frozen=True)
class TechnicalLog:
    event: LogEvent
    include_traceback: bool = True


@dataclass(frozen=True)
class UserEvent:
    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    run_id: str | None = None
    macro_id: str | None = None
    code: str | None = None
    extra: dict[str, LogExtraValue] = field(default_factory=dict)


class LoggerPort(Protocol):
    def bind_context(self, context: RunLogContext) -> LoggerPort: ...

    def technical(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str = "log.message",
        extra: dict[str, LogExtraValue] | None = None,
        exc: BaseException | None = None,
    ) -> None: ...

    def user(
        self,
        level: str,
        message: str,
        *,
        component: str,
        event: str,
        code: str | None = None,
        extra: dict[str, LogExtraValue] | None = None,
    ) -> None: ...
