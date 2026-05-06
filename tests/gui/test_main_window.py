import pytest

from nyxpy.gui.main_window import MainWindow


@pytest.fixture
def dummy_catalog(monkeypatch):
    class DummyMacro:
        description = "dummy desc"
        tags = ["Tag1", "Tag2"]

    class DummyCatalog:
        def __init__(self, registry):
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
