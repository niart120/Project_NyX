"""標準 logger port 実装。"""

from __future__ import annotations

import traceback
from datetime import datetime

from nyxpy.framework.core.logger.backend import NullLogBackend
from nyxpy.framework.core.logger.dispatcher import LogSinkDispatcher
from nyxpy.framework.core.logger.events import (
    LogEvent,
    LogExtraValue,
    RunLogContext,
    TechnicalLog,
    UserEvent,
    normalize_level,
)
from nyxpy.framework.core.logger.ports import LogBackend
from nyxpy.framework.core.logger.sanitizer import LogSanitizer
from nyxpy.framework.core.macro.exceptions import FrameworkError


class DefaultLogger:
    """User event と technical log を sink/backend へ配送する logger。"""

    def __init__(
        self,
        dispatcher: LogSinkDispatcher,
        sanitizer: LogSanitizer,
        backend: LogBackend | None = None,
        context: RunLogContext | None = None,
    ) -> None:
        """Dispatcher、sanitizer、backend、任意の run context を保持します。"""
        self.dispatcher = dispatcher
        self.sanitizer = sanitizer
        self.backend = backend or NullLogBackend()
        self.context = context

    def bind_context(self, context: RunLogContext) -> DefaultLogger:
        return DefaultLogger(self.dispatcher, self.sanitizer, self.backend, context)

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
        log_level = normalize_level(level)
        technical_extra = self._technical_extra(extra, exc)
        log_event = LogEvent(
            timestamp=datetime.now(),
            level=log_level,
            component=component,
            event=event,
            message=self.sanitizer.mask_text(message),
            run_id=self.context.run_id if self.context else None,
            macro_id=self.context.macro_id if self.context else None,
            extra=self.sanitizer.sanitize_extra_for_technical(technical_extra),
            exception_type=type(exc).__name__ if exc is not None else None,
            traceback="".join(traceback.format_exception(exc)) if exc is not None else None,
        )
        technical_log = TechnicalLog(log_event, include_traceback=exc is not None)
        self._emit_backend(technical_log)
        self.dispatcher.emit_technical(technical_log)

    def _technical_extra(
        self,
        extra: dict[str, LogExtraValue] | None,
        exc: BaseException | None,
    ) -> dict[str, object]:
        enriched: dict[str, object] = dict(extra or {})
        if isinstance(exc, FrameworkError):
            enriched.setdefault("error_kind", exc.kind.value)
            enriched.setdefault("error_code", exc.code)
            enriched.setdefault("error_component", exc.component)
            enriched.setdefault("recoverable", exc.recoverable)
            if exc.details:
                enriched.setdefault("error_details", exc.details)
        return enriched

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
        log_level = normalize_level(level)
        timestamp = datetime.now()
        user_event = UserEvent(
            timestamp=timestamp,
            level=log_level,
            component=component,
            event=event,
            message=self.sanitizer.mask_text(message),
            run_id=self.context.run_id if self.context else None,
            macro_id=self.context.macro_id if self.context else None,
            code=code,
            extra=self.sanitizer.sanitize_extra_for_user(extra),
        )
        self.dispatcher.emit_user(user_event)

    def _emit_backend(self, log: TechnicalLog) -> None:
        try:
            self.backend.emit_technical(log)
        except Exception as exc:
            failure = TechnicalLog(
                LogEvent(
                    timestamp=datetime.now(),
                    level=normalize_level("ERROR"),
                    component="DefaultLogger",
                    event="backend.emit_failed",
                    message="Log backend emit failed",
                    run_id=log.event.run_id,
                    macro_id=log.event.macro_id,
                    extra=self.sanitizer.sanitize_extra_for_technical(
                        {
                            "emitted_event": log.event.event,
                            "exception_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    ),
                    exception_type=type(exc).__name__,
                ),
                include_traceback=False,
            )
            self.dispatcher.emit_technical(failure)


class NullLoggerPort:
    """ログを出力しない logger port。"""

    def bind_context(self, context: RunLogContext) -> NullLoggerPort:
        return self

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
        pass

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
        pass
