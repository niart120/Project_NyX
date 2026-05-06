from __future__ import annotations

from datetime import datetime

from nyxpy.framework.core.logger import LogLevel, LogSanitizer, LogSinkDispatcher, UserEvent
from nyxpy.gui.panes.log_pane import LogPane


def test_gui_log_pane_displays_user_event_from_sink(qtbot) -> None:
    dispatcher = LogSinkDispatcher(LogSanitizer())
    pane = LogPane(dispatcher)
    qtbot.addWidget(pane)

    dispatcher.emit_user(
        UserEvent(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            component="test",
            event="macro.message",
            message="hello user",
        )
    )

    qtbot.waitUntil(lambda: "hello user" in pane.view.toPlainText())


def test_gui_log_sink_removed_on_close(qtbot) -> None:
    dispatcher = LogSinkDispatcher(LogSanitizer())
    pane = LogPane(dispatcher)
    qtbot.addWidget(pane)

    pane.close()

    dispatcher.emit_user(
        UserEvent(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            component="test",
            event="macro.message",
            message="after close",
        )
    )
    assert "after close" not in pane.view.toPlainText()
