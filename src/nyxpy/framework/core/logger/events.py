"""ログ event と log level の model。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from nyxpy.framework.core.macro.exceptions import FrameworkValue

type LogExtraValue = FrameworkValue


class LogLevel(StrEnum):
    """Logger が扱う severity level。"""

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
    """文字列または `LogLevel` を正規化します。"""
    try:
        return level if isinstance(level, LogLevel) else LogLevel(level.upper())
    except ValueError as exc:
        raise ValueError(f"invalid log level: {level}") from exc


def level_enabled(level: LogLevel, minimum: LogLevel) -> bool:
    """指定 level が minimum 以上なら `True` を返します。"""
    return _LEVEL_ORDER[level] >= _LEVEL_ORDER[minimum]


@dataclass(frozen=True)
class RunLogContext:
    """単一 macro run に紐づく log context。"""

    run_id: str
    macro_id: str
    macro_name: str = ""
    entrypoint: str = "runtime"
    started_at: datetime | None = None


@dataclass(frozen=True)
class LogEvent:
    """Backend と technical sink へ送る構造化 log event。"""

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
    """Traceback 出力方針を伴う technical log payload。"""

    event: LogEvent
    include_traceback: bool = True


@dataclass(frozen=True)
class UserEvent:
    """GUI や console へ提示する利用者向け event。"""

    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    run_id: str | None = None
    macro_id: str | None = None
    code: str | None = None
    extra: dict[str, LogExtraValue] = field(default_factory=dict)
