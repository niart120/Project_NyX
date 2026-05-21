"""JSONL 形式の技術ログ backend。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from threading import RLock

from nyxpy.framework.core.logger.events import (
    LogEvent,
    TechnicalLog,
    level_enabled,
    normalize_level,
)
from nyxpy.framework.core.logger.rotation import RotationPolicy, rotate_if_needed


class NullLogBackend:
    """技術ログを破棄する backend。"""

    def emit_technical(self, event: TechnicalLog) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class JsonlLogBackend:
    """技術ログを単一 JSONL ファイルへ保存する backend。"""

    def __init__(
        self,
        path: Path,
        *,
        level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 3,
        retention_days: int = 30,
    ) -> None:
        """出力 path と rotation 方針を保持し、親 directory を作成します。"""
        self.path = Path(path)
        self.minimum_level = normalize_level(level)
        self.rotation = RotationPolicy(
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
        )
        self._lock = RLock()
        self._closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rotate_if_needed(self.path, self.rotation)

    def set_level(self, level: str) -> None:
        self.minimum_level = normalize_level(level)

    def emit_technical(self, event: TechnicalLog) -> None:
        if not level_enabled(event.event.level, self.minimum_level):
            return
        with self._lock:
            if self._closed:
                return
            rotate_if_needed(self.path, self.rotation)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(_event_to_json(event.event), ensure_ascii=False) + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        with self._lock:
            self._closed = True


def _event_to_json(event: LogEvent) -> dict:
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["level"] = event.level.value
    return json.loads(json.dumps(payload, ensure_ascii=False, default=repr))
