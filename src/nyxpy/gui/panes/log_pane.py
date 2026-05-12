from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.logger import LogSinkDispatcher, UserEvent
from nyxpy.gui.log_sink import GuiLogSink, connect_user_event


class LogPane(QWidget):
    """
    Pane for displaying real-time user logs in a read-only text view.
    """

    def __init__(self, dispatcher: LogSinkDispatcher, parent=None):
        super().__init__(parent)
        self.dispatcher = dispatcher
        self.gui_sink = GuiLogSink(self)
        self.gui_sink_id: str | None = self.dispatcher.add_sink(
            self.gui_sink,
            level=("DEBUG" if self.debug_enabled else "INFO"),
        )

        main_layout = QVBoxLayout(self)
        control_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("自動スクロール", self)
        self.auto_scroll_checkbox.setChecked(True)
        self.debug_checkbox = QCheckBox("デバッグログ表示", self)
        self.debug_checkbox.setChecked(False)
        self.clear_button = QPushButton("Clear", self)
        control_layout.addWidget(self.auto_scroll_checkbox)
        control_layout.addWidget(self.debug_checkbox)
        control_layout.addWidget(self.clear_button)
        control_layout.addStretch(1)
        main_layout.addLayout(control_layout)

        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumWidth(0)
        self.setMinimumWidth(0)
        main_layout.addWidget(self.view)

        self.clear_button.clicked.connect(self.view.clear)
        connect_user_event(self.gui_sink, self._append_event_to_view)
        self.debug_checkbox.stateChanged.connect(self._on_debug_checkbox_changed)

    @property
    def debug_enabled(self) -> bool:
        return hasattr(self, "debug_checkbox") and self.debug_checkbox.isChecked()

    def _append_event_to_view(self, event: UserEvent) -> None:
        self.view.appendPlainText(self._format_event(event))
        if self.auto_scroll_checkbox.isChecked():
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def _format_event(self, event: UserEvent) -> str:
        return f"{event.timestamp:%H:%M:%S} | {event.level} | {event.message}"

    def dispose(self) -> None:
        if self.gui_sink_id is None:
            return
        self.dispatcher.remove_sink(self.gui_sink_id)
        self.gui_sink_id = None
        self.gui_sink.stop()

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)

    def _on_debug_checkbox_changed(self, state):
        if self.gui_sink_id is None:
            return
        level = "DEBUG" if self.debug_checkbox.isChecked() else "INFO"
        self.dispatcher.set_level(self.gui_sink_id, level)
