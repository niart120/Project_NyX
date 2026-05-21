"""ログ API の port 定義。"""

from __future__ import annotations

from abc import ABC
from typing import Protocol

from nyxpy.framework.core.logger.events import (
    LogEvent,
    LogExtraValue,
    LogLevel,
    RunLogContext,
    TechnicalLog,
    UserEvent,
)


class LoggerPort(Protocol):
    """Framework 各層が依存する logger port protocol。"""

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


class LogSink(ABC):
    """User event と technical log を受け取る sink の基底 class。"""

    def emit_technical(self, event: TechnicalLog) -> None:
        pass

    def emit_user(self, event: UserEvent) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class LogBackend(Protocol):
    """Technical log の永続化 backend protocol。"""

    def emit_technical(self, event: TechnicalLog) -> None: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


__all__ = [
    "LogBackend",
    "LogEvent",
    "LogExtraValue",
    "LoggerPort",
    "LogLevel",
    "LogSink",
    "RunLogContext",
    "TechnicalLog",
    "UserEvent",
]
