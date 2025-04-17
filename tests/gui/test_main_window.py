import pytest
from PySide6.QtCore import Qt
from nyxpy.gui.main_window import MainWindow

@pytest.fixture
def dummy_executor(monkeypatch):
    class DummyMacro:
        description = "dummy desc"
        tags = ["Tag1", "Tag2"]
    class DummyExecutor:
        def __init__(self):
            self.macros = {"DummyMacro": DummyMacro()}
    monkeypatch.setattr('nyxpy.gui.main_window.MacroExecutor', DummyExecutor)
    yield

@pytest.fixture
def window(qtbot, dummy_executor):
    w = MainWindow()
    qtbot.addWidget(w)
    return w

def test_initial_ui_state(window):
    assert window.table.rowCount() == 1
    assert window.table.item(0,0).text() == "DummyMacro"
    assert window.status_label.text() == "準備完了"
    assert not window.run_btn.isEnabled()
    assert not window.cancel_btn.isEnabled()
    assert window.snapshot_btn.isEnabled()
    assert window.tag_list.count() == 2

def test_run_button_enabled_on_selection(window, qtbot):
    # simulate selecting the first row
    window.table.selectRow(0)
    assert window.run_btn.isEnabled()

def test_search_filter(window):
    # type a non-matching keyword
    window.search_box.setText("nomatch")
    assert window.table.isRowHidden(0)
    window.search_box.clear()
    assert not window.table.isRowHidden(0)

def test_tag_filter(window):
    # check Tag1
    item = window.tag_list.findItems("Tag1", Qt.MatchExactly)[0]
    item.setCheckState(Qt.Checked)
    assert not window.table.isRowHidden(0)
    item.setCheckState(Qt.Unchecked)
    assert not window.table.isRowHidden(0)
