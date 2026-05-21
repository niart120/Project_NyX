"""ログ event を受け取る sink 実装。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import TextIO

from nyxpy.framework.core.logger.events import LogEvent, TechnicalLog, UserEvent
from nyxpy.framework.core.logger.ports import LogSink
from nyxpy.framework.core.logger.rotation import (
    RotationPolicy,
    cleanup_retention_glob,
    rotate_if_needed,
)


class TestLogSink(LogSink):
    __test__ = False

    def __init__(self) -> None:
        self.technical_logs: list[TechnicalLog] = []
        self.user_events: list[UserEvent] = []
        self.flushed = False
        self.closed = False

    def emit_technical(self, event: TechnicalLog) -> None:
        self.technical_logs.append(event)

    def emit_user(self, event: UserEvent) -> None:
        self.user_events.append(event)

    def flush(self) -> None:
        self.flushed = True

    def close(self) -> None:
        self.closed = True


class ConsoleLogSink(LogSink):
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def emit_user(self, event: UserEvent) -> None:
        print(self._format_user(event), file=self.stream)

    def emit_technical(self, event: TechnicalLog) -> None:
        log_event = event.event
        if log_event.level in {"ERROR", "CRITICAL"}:
            print(self._format_technical(log_event), file=self.stream)

    def _format_user(self, event: UserEvent) -> str:
        return f"{event.timestamp:%Y-%m-%d %H:%M:%S} | {event.level} | {event.message}"

    def _format_technical(self, event: LogEvent) -> str:
        return (
            f"{event.timestamp:%Y-%m-%d %H:%M:%S} | {event.level} | "
            f"{event.component} | {event.event} | {event.message}"
        )


class TextFileLogSink(LogSink):
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 3,
        retention_days: int = 14,
    ) -> None:
        self.path = Path(path)
        self.rotation = RotationPolicy(
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
        )
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rotate_if_needed(self.path, self.rotation)

    def emit_technical(self, event: TechnicalLog) -> None:
        log_event = event.event
        line = (
            f"{log_event.timestamp.isoformat()} | {log_event.level} | "
            f"{log_event.component} | {log_event.event} | {log_event.message}"
        )
        self._write_line(line)

    def emit_user(self, event: UserEvent) -> None:
        line = (
            f"{event.timestamp.isoformat()} | {event.level} | "
            f"{event.component} | {event.event} | {event.message}"
        )
        self._write_line(line)

    def _write_line(self, line: str) -> None:
        with self._lock:
            if self._closed:
                return
            rotate_if_needed(self.path, self.rotation)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        with self._lock:
            self._closed = True


class JsonlFileSink(LogSink):
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 3,
        retention_days: int = 30,
    ) -> None:
        self.path = Path(path)
        self.rotation = RotationPolicy(
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
        )
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rotate_if_needed(self.path, self.rotation)

    def emit_technical(self, event: TechnicalLog) -> None:
        self._write_event(_event_to_json(event.event, kind="technical"))

    def emit_user(self, event: UserEvent) -> None:
        self._write_event(_user_event_to_json(event))

    def _write_event(self, payload: dict) -> None:
        with self._lock:
            if self._closed:
                return
            rotate_if_needed(self.path, self.rotation)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        with self._lock:
            self._closed = True


class RunJsonlFileSink(LogSink):
    def __init__(
        self,
        base_dir: Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 3,
        retention_days: int = 30,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.rotation = RotationPolicy(
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
        )
        self._lock = RLock()
        self._closed = False
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_retention()

    def emit_technical(self, event: TechnicalLog) -> None:
        log_event = event.event
        if log_event.run_id is None:
            return
        self._write_event(
            timestamp=log_event.timestamp,
            run_id=log_event.run_id,
            payload=_event_to_json(log_event, kind="technical"),
        )

    def emit_user(self, event: UserEvent) -> None:
        if event.run_id is None:
            return
        self._write_event(
            timestamp=event.timestamp,
            run_id=event.run_id,
            payload=_user_event_to_json(event),
        )

    def _write_event(self, *, timestamp, run_id: str, payload: dict) -> None:
        day_dir = self.base_dir / f"{timestamp:%Y%m%d}"
        path = day_dir / f"{run_id}.jsonl"
        with self._lock:
            if self._closed:
                return
            day_dir.mkdir(parents=True, exist_ok=True)
            rotate_if_needed(path, self.rotation)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _cleanup_retention(self) -> None:
        cleanup_retention_glob(self.base_dir, "*/*.jsonl*", self.rotation.retention_days)


def _event_to_json(event: LogEvent, *, kind: str | None = None) -> dict:
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["level"] = event.level.value
    if kind is not None:
        payload["kind"] = kind
    return payload


def _user_event_to_json(event: UserEvent) -> dict:
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["level"] = event.level.value
    payload["kind"] = "user"
    return payload
