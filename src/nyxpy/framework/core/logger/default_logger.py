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


class DefaultLogger:
    def __init__(
        self,
        dispatcher: LogSinkDispatcher,
        sanitizer: LogSanitizer,
        backend: LogBackend | None = None,
        context: RunLogContext | None = None,
    ) -> None:
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
        log_event = LogEvent(
            timestamp=datetime.now(),
            level=log_level,
            component=component,
            event=event,
            message=self.sanitizer.mask_text(message),
            run_id=self.context.run_id if self.context else None,
            macro_id=self.context.macro_id if self.context else None,
            extra=self.sanitizer.sanitize_extra_for_technical(extra),
            exception_type=type(exc).__name__ if exc is not None else None,
            traceback="".join(traceback.format_exception(exc)) if exc is not None else None,
        )
        technical_log = TechnicalLog(log_event, include_traceback=exc is not None)
        self._emit_backend(technical_log)
        self.dispatcher.emit_technical(technical_log)

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
        technical_log = TechnicalLog(
            LogEvent(
                timestamp=timestamp,
                level=log_level,
                component=component,
                event=event,
                message=self.sanitizer.mask_text(message),
                run_id=user_event.run_id,
                macro_id=user_event.macro_id,
                extra=self.sanitizer.sanitize_extra_for_technical(extra),
            ),
            include_traceback=False,
        )
        self._emit_backend(technical_log)
        self.dispatcher.emit_technical(technical_log)

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
