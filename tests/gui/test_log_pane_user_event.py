from __future__ import annotations

from datetime import datetime

from nyxpy.framework.core.logger import (
    LogEvent,
    LogLevel,
    LogSanitizer,
    LogSinkDispatcher,
    TechnicalLog,
    UserEvent,
)
from nyxpy.gui.panes.log_pane import LogPane


def test_gui_log_pane_displays_user_event_from_sink(qtbot) -> None:
    dispatcher = LogSinkDispatcher(LogSanitizer())
    pane = LogPane(dispatcher, kind="macro")
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


def test_debug_log_is_separated_from_macro_log(qtbot) -> None:
    dispatcher = LogSinkDispatcher(LogSanitizer())
    macro_pane = LogPane(dispatcher, kind="macro")
    tool_pane = LogPane(dispatcher, kind="tool")
    qtbot.addWidget(macro_pane)
    qtbot.addWidget(tool_pane)

    dispatcher.emit_user(
        UserEvent(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            component="MacroRunner",
            event="macro.message",
            message="macro line",
        )
    )
    dispatcher.emit_technical(
        TechnicalLog(
            LogEvent(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                component="tool",
                event="tool.message",
                message="tool line",
            )
        )
    )

    qtbot.waitUntil(lambda: "macro line" in macro_pane.view.toPlainText())
    qtbot.waitUntil(lambda: "tool line" in tool_pane.view.toPlainText())
    assert "tool line" not in macro_pane.view.toPlainText()
    assert "macro line" not in tool_pane.view.toPlainText()
