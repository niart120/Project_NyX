import re
from pathlib import Path
import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from nyxpy.gui.main_window import MainWindow

@pytest.fixture
def tmp_cwd_and_dummy(monkeypatch, tmp_path):
    # isolate cwd and dummy executor
    monkeypatch.chdir(tmp_path)
    class DummyMacro:
        description = ""
        tags = []
    class DummyExecutor:
        def __init__(self): self.macros = {"Dummy": DummyMacro()}
    monkeypatch.setattr('nyxpy.gui.main_window.MacroExecutor', DummyExecutor)
    yield tmp_path

@pytest.fixture
def window(qtbot, tmp_cwd_and_dummy):
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    qtbot.addWidget(w)
    return w

def test_take_snapshot_creates_file_and_updates_status(window, tmp_cwd_and_dummy):
    # Provide a dummy pixmap
    pix = QPixmap(10, 10)
    window.preview_label.setPixmap(pix)
    # Execute snapshot
    window.take_snapshot()
    snaps_dir = tmp_cwd_and_dummy / 'snapshots'
    files = list(snaps_dir.iterdir())
    assert len(files) == 1
    fname = files[0].name
    assert re.match(r"\d{8}_\d{6}\.png", fname)
    # Status label update
    assert window.status_label.text().startswith("スナップショット保存: ")
