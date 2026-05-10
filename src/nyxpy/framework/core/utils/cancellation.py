import threading
import time
from datetime import datetime

from nyxpy.framework.core.macro.exceptions import ConfigurationError, MacroCancelled


class CancellationToken:
    """
    中断要求を管理するためのクラス。
    内部にスレッドセーフなイベントを保持し、中断状態を示す。
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._reason: str | None = None
        self._source: str | None = None
        self._requested_at: datetime | None = None

    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def request_stop(self) -> None:
        self.request_cancel(reason="stop requested", source="request_stop")

    def request_cancel(self, reason: str = "", source: str = "") -> None:
        with self._lock:
            if self._stop_event.is_set():
                return
            self._reason = reason
            self._source = source
            self._requested_at = datetime.now()
            self._stop_event.set()

    def clear(self) -> None:
        with self._lock:
            self._reason = None
            self._source = None
            self._requested_at = None
            self._stop_event.clear()

    def reason(self) -> str | None:
        return self._reason

    def source(self) -> str | None:
        return self._source

    def requested_at(self) -> datetime | None:
        return self._requested_at

    def wait(self, timeout: float) -> bool:
        return self._stop_event.wait(timeout)

    def throw_if_requested(self) -> None:
        if not self.stop_requested():
            return
        reason = self.reason() or "Macro execution interrupted."
        raise MacroCancelled(
            reason,
            component="CancellationToken",
            details={"reason": reason, "source": self.source() or ""},
        )


def cancellation_aware_wait(seconds: float, token: CancellationToken) -> bool:
    if seconds < 0:
        raise ConfigurationError(
            "wait seconds must be greater than or equal to 0",
            code="NYX_INVALID_WAIT_SECONDS",
            component="Command.wait",
        )

    token.throw_if_requested()
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            token.throw_if_requested()
            return True
        if token.wait(timeout=min(0.05, remaining)):
            return False
