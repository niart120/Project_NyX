from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from nyxpy.framework.core.macro.exceptions import FrameworkValue

type LogExtraValue = FrameworkValue


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


_LEVEL_ORDER = {
    LogLevel.DEBUG: 10,
    LogLevel.INFO: 20,
    LogLevel.WARNING: 30,
    LogLevel.ERROR: 40,
    LogLevel.CRITICAL: 50,
}


def normalize_level(level: str | LogLevel) -> LogLevel:
    try:
        return level if isinstance(level, LogLevel) else LogLevel(level.upper())
    except ValueError as exc:
        raise ValueError(f"invalid log level: {level}") from exc


def level_enabled(level: LogLevel, minimum: LogLevel) -> bool:
    return _LEVEL_ORDER[level] >= _LEVEL_ORDER[minimum]


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
