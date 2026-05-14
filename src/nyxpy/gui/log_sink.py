from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal

from nyxpy.framework.core.logger import TechnicalLog, UserEvent


class GuiLogSink(QObject):
    technical_event = Signal(object)
    user_event = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stopped = False

    def emit_user(self, event: UserEvent) -> None:
        if self._stopped:
            return
        try:
            self.user_event.emit(event)
        except RuntimeError:
            self._stopped = True

    def emit_technical(self, event: TechnicalLog) -> None:
        if self._stopped:
            return
        try:
            self.technical_event.emit(event)
        except RuntimeError:
            self._stopped = True

    def stop(self) -> None:
        self._stopped = True


def connect_technical_event(sink: GuiLogSink, slot) -> None:
    sink.technical_event.connect(slot, Qt.ConnectionType.QueuedConnection)


def connect_user_event(sink: GuiLogSink, slot) -> None:
    sink.user_event.connect(slot, Qt.ConnectionType.QueuedConnection)
