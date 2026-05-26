"""マクロ実行結果の model。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from nyxpy.framework.core.io.resources import ResourceRef
from nyxpy.framework.core.macro.exceptions import ErrorInfo


class RunStatus(StrEnum):
    """Macro run の最終状態。"""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CleanupWarning(Exception):
    """Run 終了後の port cleanup 失敗を結果に残す warning。"""

    port_name: str
    exception_type: str
    message: str

    def __init__(self, port_name: str, exception_type: str, message: str) -> None:
        """Cleanup 失敗元 port、例外型、message を保持します。"""
        super().__init__(message)
        self.port_name = port_name
        self.exception_type = exception_type
        self.message = message


@dataclass(frozen=True)
class RunResult:
    """Macro run の結果、error 情報、cleanup warning。"""

    run_id: str
    macro_id: str
    macro_name: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    error: ErrorInfo | None = None
    cleanup_warnings: tuple[CleanupWarning, ...] = ()
    artifacts: tuple[ResourceRef, ...] = ()
    artifacts_overflow_count: int = 0

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.SUCCESS and self.error is None

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()
