import pytest
from unittest.mock import patch
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
def patched_managers():
    # キャプチャマネージャとシリアルマネージャの非同期動作をパッチ
    with patch('nyxpy.framework.core.hardware.capture.CaptureManager') as mock_cap_mgr:
        with patch('nyxpy.framework.core.hardware.serial_comm.SerialManager') as mock_ser_mgr:
            # 同期的にデバイス検出するように動作を変更
            mock_cap_mgr.return_value.auto_register_devices.side_effect = lambda: None
            mock_ser_mgr.return_value.auto_register_devices.side_effect = lambda: None
            yield mock_cap_mgr, mock_ser_mgr

@pytest.fixture
def window(qtbot, dummy_executor, patched_managers):
    # パッチされたマネージャーを使用
    mock_cap_mgr, mock_ser_mgr = patched_managers
    
    # モックのキャプチャマネージャを設定
    mock_cap_mgr.return_value.list_devices.return_value = ["ダミーデバイス"]
    
    w = MainWindow()
    qtbot.addWidget(w)
    
    # 非同期初期化を手動で完了させる
    w.deferred_init()
    
    # ステータスラベルを準備完了に手動で更新
    w.status_label.setText("準備完了")
    
    return w

def test_initial_ui_state(window):
    assert window.macro_browser.table.rowCount() == 1
    assert window.macro_browser.table.item(0,0).text() == "DummyMacro"
    assert window.status_label.text() == "準備完了"
    assert not window.control_pane.run_btn.isEnabled()
    assert not window.control_pane.cancel_btn.isEnabled()
    assert window.control_pane.snapshot_btn.isEnabled()
    assert window.macro_browser.tag_list.count() == 2

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

def test_tag_filter(window):
    # check Tag1
    item = window.macro_browser.tag_list.findItems("Tag1", Qt.MatchExactly)[0]
    item.setCheckState(Qt.Checked)
    assert not window.macro_browser.table.isRowHidden(0)
    item.setCheckState(Qt.Unchecked)
    assert not window.macro_browser.table.isRowHidden(0)
