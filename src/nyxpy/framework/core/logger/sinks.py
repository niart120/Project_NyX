from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import TextIO

from nyxpy.framework.core.logger.events import LogEvent, TechnicalLog, UserEvent
from nyxpy.framework.core.logger.ports import LogSink


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
        retention_days: int = 14,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_retention()

    def emit_technical(self, event: TechnicalLog) -> None:
        log_event = event.event
        line = (
            f"{log_event.timestamp.isoformat()} | {log_event.level} | "
            f"{log_event.component} | {log_event.event} | {log_event.message}"
        )
        self._write_line(line)

    def _write_line(self, line: str) -> None:
        with self._lock:
            if self._closed:
                return
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _rotate_if_needed(self) -> None:
        if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
            rotated = self.path.with_suffix(self.path.suffix + ".1")
            if rotated.exists():
                rotated.unlink()
            self.path.replace(rotated)

    def _cleanup_retention(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for candidate in self.path.parent.glob(self.path.name + "*"):
            if datetime.fromtimestamp(candidate.stat().st_mtime) < cutoff:
                candidate.unlink()


class JsonlFileSink(LogSink):
    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        retention_days: int = 30,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_retention()

    def emit_technical(self, event: TechnicalLog) -> None:
        self._write_event(event.event)

    def _write_event(self, event: LogEvent) -> None:
        with self._lock:
            if self._closed:
                return
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(_event_to_json(event), ensure_ascii=False) + "\n")

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _rotate_if_needed(self) -> None:
        if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
            rotated = self.path.with_suffix(self.path.suffix + ".1")
            if rotated.exists():
                rotated.unlink()
            self.path.replace(rotated)

    def _cleanup_retention(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for candidate in self.path.parent.glob(self.path.name + "*"):
            if datetime.fromtimestamp(candidate.stat().st_mtime) < cutoff:
                candidate.unlink()


class RunJsonlFileSink(LogSink):
    def __init__(self, base_dir: Path, *, retention_days: int = 30) -> None:
        self.base_dir = Path(base_dir)
        self.retention_days = retention_days
        self._lock = RLock()
        self._closed = False
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_retention()

    def emit_technical(self, event: TechnicalLog) -> None:
        log_event = event.event
        if log_event.run_id is None:
            return
        day_dir = self.base_dir / f"{log_event.timestamp:%Y%m%d}"
        path = day_dir / f"{log_event.run_id}.jsonl"
        with self._lock:
            if self._closed:
                return
            day_dir.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(_event_to_json(log_event), ensure_ascii=False) + "\n")

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _cleanup_retention(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for candidate in self.base_dir.glob("*/*.jsonl"):
            if datetime.fromtimestamp(candidate.stat().st_mtime) < cutoff:
                candidate.unlink()


def _event_to_json(event: LogEvent) -> dict:
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["level"] = event.level.value
    return payload
