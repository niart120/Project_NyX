from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from nyxpy.framework.core.logger.events import (
    LogEvent,
    LogLevel,
    TechnicalLog,
    UserEvent,
    level_enabled,
    normalize_level,
)
from nyxpy.framework.core.logger.ports import LogSink
from nyxpy.framework.core.logger.sanitizer import LogSanitizer


@dataclass(frozen=True)
class _SinkRegistration:
    sink_id: str
    sink: LogSink
    level: LogLevel


class LogSinkDispatcher:
    def __init__(self, sanitizer: LogSanitizer, *, lock_timeout_sec: float = 1.0) -> None:
        self.sanitizer = sanitizer
        self.lock_timeout_sec = lock_timeout_sec
        self._sink_lock = threading.RLock()
        self._sinks: dict[str, _SinkRegistration] = {}
        self._failure_state = threading.local()

    def add_sink(self, sink: LogSink, *, level: str = "INFO") -> str:
        sink_id = uuid4().hex
        self._with_lock(
            lambda: self._sinks.__setitem__(
                sink_id, _SinkRegistration(sink_id, sink, normalize_level(level))
            )
        )
        return sink_id

    def set_level(self, sink_id: str, level: str) -> None:
        def update() -> None:
            registration = self._sinks[sink_id]
            self._sinks[sink_id] = _SinkRegistration(
                sink_id,
                registration.sink,
                normalize_level(level),
            )

        self._with_lock(update)

    def remove_sink(self, sink_id: str) -> None:
        self._with_lock(lambda: self._sinks.pop(sink_id, None))

    def emit_technical(self, event: TechnicalLog) -> None:
        for registration in self._snapshot(event.event.level):
            try:
                registration.sink.emit_technical(event)
            except Exception as exc:
                self._record_sink_failure(registration, event.event.event, exc)

    def emit_user(self, event: UserEvent) -> None:
        for registration in self._snapshot(event.level):
            try:
                registration.sink.emit_user(event)
            except Exception as exc:
                self._record_sink_failure(registration, event.event, exc)

    def flush(self) -> None:
        for registration in self._snapshot_all():
            try:
                registration.sink.flush()
            except Exception as exc:
                self._record_sink_failure(registration, "sink.flush", exc)

    def close(self) -> None:
        for registration in self._snapshot_all():
            try:
                registration.sink.close()
            except Exception as exc:
                self._record_sink_failure(registration, "sink.close", exc)

    def _snapshot(self, level: LogLevel) -> tuple[_SinkRegistration, ...]:
        return tuple(
            registration
            for registration in self._snapshot_all()
            if level_enabled(level, registration.level)
        )

    def _snapshot_all(self) -> tuple[_SinkRegistration, ...]:
        registrations: tuple[_SinkRegistration, ...] = ()

        def copy() -> None:
            nonlocal registrations
            registrations = tuple(self._sinks.values())

        self._with_lock(copy)
        return registrations

    def _with_lock(self, callback) -> None:
        acquired = self._sink_lock.acquire(timeout=self.lock_timeout_sec)
        if not acquired:
            self._fallback_stderr("logging.sink_lock_timeout", "sink lock timeout")
            return
        try:
            callback()
        finally:
            self._sink_lock.release()

    def _record_sink_failure(
        self,
        failed: _SinkRegistration,
        emitted_event: str,
        exc: Exception,
    ) -> None:
        if getattr(self._failure_state, "active", False):
            self._fallback_stderr("sink.emit_failed", f"{type(exc).__name__}: {exc}")
            return
        self._failure_state.active = True
        try:
            failure = TechnicalLog(
                LogEvent(
                    timestamp=datetime.now(),
                    level=LogLevel.ERROR,
                    component="LogSinkDispatcher",
                    event="sink.emit_failed",
                    message="Log sink emit failed",
                    extra=self.sanitizer.sanitize_extra_for_technical(
                        {
                            "sink_id": failed.sink_id,
                            "emitted_event": emitted_event,
                            "exception_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    ),
                    exception_type=type(exc).__name__,
                ),
                include_traceback=False,
            )
            delivered = False
            for registration in self._snapshot(LogLevel.ERROR):
                if registration.sink_id == failed.sink_id:
                    continue
                try:
                    registration.sink.emit_technical(failure)
                    delivered = True
                except Exception as nested:
                    self._fallback_stderr("sink.emit_failed", f"{type(nested).__name__}: {nested}")
            if not delivered:
                self._fallback_stderr("sink.emit_failed", f"{type(exc).__name__}: {exc}")
        finally:
            self._failure_state.active = False

    def _fallback_stderr(self, code: str, message: str) -> None:
        safe_message = self.sanitizer.mask_text(message)
        print(
            f"nyxpy logging fallback code={code} component=LogSinkDispatcher message={safe_message}",
            file=sys.stderr,
        )
