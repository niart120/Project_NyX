from unittest.mock import MagicMock

import pytest

from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.gui.main_window import MainWindow


@pytest.fixture
def dummy_catalog(monkeypatch):
    class DummyMacro:
        description = "dummy desc"
        tags = ["Tag1", "Tag2"]

    class DummyCatalog:
        def __init__(self, registry):
            self.macros = {"DummyMacro": DummyMacro()}

        def reload_macros(self) -> None:
            self.macros = {"DummyMacro": DummyMacro()}

    monkeypatch.setattr("nyxpy.gui.main_window.MacroCatalog", DummyCatalog)
    yield


@pytest.fixture
def window(qtbot, dummy_catalog):
    # conftest の _no_real_hardware で initialize_managers は no-op 化済み
    w = MainWindow()
    qtbot.addWidget(w)

    # 非同期初期化を手動で完了させる
    w.deferred_init()

    # ステータスラベルを準備完了に手動で更新
    w.status_label.setText("準備完了")

    yield w

    # teardown: プレビュータイマーを確実に停止
    w.preview_pane.timer.stop()


def test_initial_ui_state(window):
    assert window.macro_browser.table.rowCount() == 1
    assert window.macro_browser.table.item(0, 0).text() == "DummyMacro"
    assert window.status_label.text() == "準備完了"
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()
    assert window.control_pane.snapshot_btn.isEnabled()


def test_run_button_enabled_on_selection(window, qtbot):
    # simulate selecting the first row
    window.macro_browser.table.selectRow(0)
    assert window.control_pane.run_btn.isEnabled()


def test_search_filter(window):
    # type a non-matching keyword
    window.macro_browser.search_box.setText("nomatch")
    assert window.macro_browser.table.isRowHidden(0)
    window.macro_browser.search_box.clear()
    assert not window.macro_browser.table.isRowHidden(0)


class FakeRunHandle:
    def __init__(self, result: RunResult | None = None, *, done: bool = False) -> None:
        self._result = result
        self._done = done
        self.cancelled = False
        self.wait_called_with = None

    @property
    def run_id(self) -> str:
        return "run-1"

    @property
    def cancellation_token(self):
        return None

    def cancel(self) -> None:
        self.cancelled = True

    def done(self) -> bool:
        return self._done

    def wait(self, timeout=None) -> bool:
        self.wait_called_with = timeout
        return self._done

    def result(self):
        if self._result is None:
            raise RuntimeError("no result")
        return self._result


def run_result(status: RunStatus) -> RunResult:
    from datetime import datetime

    now = datetime.now()
    return RunResult(
        run_id="run-1",
        macro_id="DummyMacro",
        macro_name="DummyMacro",
        status=status,
        started_at=now,
        finished_at=now,
    )


def test_main_window_uses_run_handle(window, monkeypatch):
    handle = FakeRunHandle()
    builder = type("Builder", (), {"start": MagicMock(return_value=handle)})()
    monkeypatch.setattr(window, "_create_runtime_builder", lambda: builder)
    window.macro_browser.table.selectRow(0)

    window._start_macro({"count": 1})

    assert window.run_handle is handle
    request = builder.start.call_args.args[0]
    assert request.macro_id == "DummyMacro"
    assert request.entrypoint == "gui"
    assert request.exec_args == {"count": 1}
    assert window.control_pane.cancel_btn.isEnabled()


def test_main_window_cancel_calls_handle_cancel(window):
    handle = FakeRunHandle(done=False)
    window.run_handle = handle

    window.cancel_macro()

    assert handle.cancelled is True
    assert window.status_label.text() == "中断要求中"


def test_main_window_poll_updates_status_from_run_result(window):
    window.run_handle = FakeRunHandle(run_result(RunStatus.SUCCESS), done=True)
    window.control_pane.set_running(True)

    window._poll_run_handle()

    assert window.status_label.text() == "完了"
    assert window.run_handle is None
    assert window.last_run_result.status is RunStatus.SUCCESS
