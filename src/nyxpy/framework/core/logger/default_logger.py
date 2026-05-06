from __future__ import annotations

import traceback
from datetime import datetime

from nyxpy.framework.core.logger.dispatcher import LogSinkDispatcher
from nyxpy.framework.core.logger.events import (
    LogEvent,
    LogExtraValue,
    RunLogContext,
    TechnicalLog,
    UserEvent,
    normalize_level,
)
from nyxpy.framework.core.logger.sanitizer import LogSanitizer


class DefaultLogger:
    def __init__(
        self,
        dispatcher: LogSinkDispatcher,
        sanitizer: LogSanitizer,
        context: RunLogContext | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.sanitizer = sanitizer
        self.context = context

    def bind_context(self, context: RunLogContext) -> DefaultLogger:
        return DefaultLogger(self.dispatcher, self.sanitizer, context)

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
        self.dispatcher.emit_technical(TechnicalLog(log_event, include_traceback=exc is not None))

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
        self.dispatcher.emit_technical(
            TechnicalLog(
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
        )


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
