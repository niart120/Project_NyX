"""framework log event を Qt signal へ接続する sink。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal

from nyxpy.framework.core.logger import TechnicalLog, UserEvent


class GuiLogSink(QObject):
    """Framework log event を Qt signal として GUI thread へ渡す sink。"""

    technical_event = Signal(object)
    user_event = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Qt parent と停止 flag を初期化します。"""
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

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.stop()


def connect_technical_event(sink: GuiLogSink, slot) -> None:
    """技術ログ signal を queued connection で slot へ接続します。"""
    sink.technical_event.connect(slot, Qt.ConnectionType.QueuedConnection)


def connect_user_event(sink: GuiLogSink, slot) -> None:
    """ユーザ向けログ signal を queued connection で slot へ接続します。"""
    sink.user_event.connect(slot, Qt.ConnectionType.QueuedConnection)
