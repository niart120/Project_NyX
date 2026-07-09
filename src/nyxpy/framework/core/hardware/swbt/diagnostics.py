"""swbt diagnostics writer adapter。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

from nyxpy.framework.core.logger.ports import LoggerPort


class LoggerDiagnosticsWriter:
    """swbt diagnostics trace を NyX technical log へ流す writer。"""

    def __init__(self, logger: LoggerPort) -> None:
        """出力先 logger を保持する。"""
        self._logger = logger

    def write(self, text: str) -> int:
        """Trace text を行単位で technical log に記録する。"""
        for line in text.splitlines():
            if line:
                self._logger.technical(
                    "DEBUG",
                    line,
                    component="SwbtDiagnostics",
                    event="swbt.diagnostics",
                )
        return len(text)

    def flush(self) -> None:
        """Logger 出力には明示 flush がないため何もしない。"""


class TeeDiagnosticsWriter:
    """複数 writer へ同じ diagnostics trace を流す writer。"""

    def __init__(self, writers: Iterable[TextIO]) -> None:
        """Tee 先 writer を tuple として保持する。"""
        self._writers = tuple(writers)

    def write(self, text: str) -> int:
        """すべての writer へ text を書き込む。"""
        for writer in self._writers:
            writer.write(text)
        return len(text)

    def flush(self) -> None:
        """Flush を持つ writer へ反映する。"""
        for writer in self._writers:
            writer.flush()


def open_diagnostics_trace(path: Path) -> TextIO:
    """JSONL evidence 用 diagnostics trace file を開く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")
