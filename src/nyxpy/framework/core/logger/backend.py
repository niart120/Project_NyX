from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from nyxpy.framework.core.logger.events import (
    LogEvent,
    TechnicalLog,
    level_enabled,
    normalize_level,
)


class NullLogBackend:
    def emit_technical(self, event: TechnicalLog) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class JsonlLogBackend:
    def __init__(
        self,
        path: Path,
        *,
        level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,
        retention_days: int = 30,
    ) -> None:
        self.path = Path(path)
        self.minimum_level = normalize_level(level)
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_retention()

    def set_level(self, level: str) -> None:
        self.minimum_level = normalize_level(level)

    def emit_technical(self, event: TechnicalLog) -> None:
        if not level_enabled(event.event.level, self.minimum_level):
            return
        with self._lock:
            if self._closed:
                return
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(_event_to_json(event.event), ensure_ascii=False) + "\n")

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


def _event_to_json(event: LogEvent) -> dict:
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["level"] = event.level.value
    return json.loads(json.dumps(payload, ensure_ascii=False, default=repr))
