"""Qt event loop を止めずに同期処理を実行する小さな worker。"""

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class _Worker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.operation()
        except Exception as exc:
            self.signals.failed.emit(exc)
            return
        self.signals.succeeded.emit(result)


class BackgroundTask(QObject):
    """Worker thread の結果を owner の Qt thread へ signal で戻す。"""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        operation: Callable[[], object],
        *,
        parent: QObject | None = None,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        """実行関数、owner、任意のthread poolを保持する。"""
        super().__init__(parent)
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker = _Worker(operation)
        self._worker.signals.succeeded.connect(self._on_succeeded)
        self._worker.signals.failed.connect(self._on_failed)

    def start(self) -> None:
        self._thread_pool.start(self._worker)

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        self.succeeded.emit(result)
        self.finished.emit()

    @Slot(object)
    def _on_failed(self, error: BaseException) -> None:
        self.failed.emit(error)
        self.finished.emit()
