from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Event, Thread

from nyxpy.framework.core.runtime.result import RunResult
from nyxpy.framework.core.utils.cancellation import CancellationToken


class RunHandle(ABC):
    @property
    @abstractmethod
    def run_id(self) -> str: ...

    @property
    @abstractmethod
    def cancellation_token(self) -> CancellationToken: ...

    @abstractmethod
    def cancel(self) -> None: ...

    @abstractmethod
    def done(self) -> bool: ...

    @abstractmethod
    def wait(self, timeout: float | None = None) -> bool: ...

    @abstractmethod
    def result(self) -> RunResult: ...


class ThreadRunHandle(RunHandle):
    def __init__(
        self,
        *,
        run_id: str,
        cancellation_token: CancellationToken,
        thread: Thread,
        done_event: Event,
        result_getter,
    ) -> None:
        self._run_id = run_id
        self._cancellation_token = cancellation_token
        self._thread = thread
        self._done_event = done_event
        self._result_getter = result_getter

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def cancellation_token(self) -> CancellationToken:
        return self._cancellation_token

    def cancel(self) -> None:
        self._cancellation_token.request_cancel(reason="user cancelled", source="gui_or_cli")

    def done(self) -> bool:
        return self._done_event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._done_event.wait(timeout)

    def result(self) -> RunResult:
        if not self.done():
            raise RuntimeError("Run result is not available yet.")
        return self._result_getter()
