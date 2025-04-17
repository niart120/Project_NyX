import pytest
import numpy as np
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication
from nyxpy.gui.main_window import MainWindow

@pytest.fixture
def tmp_cwd_and_dummy(monkeypatch, tmp_path):
    # isolate cwd and patch MacroExecutor
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

class DummyDevice:
    def __init__(self, frame): self._frame = frame
    def get_frame(self): return self._frame


def test_update_preview_success(window):
    # Prepare dummy frame 10x20x3
    frame = np.full((10, 20, 3), 128, dtype=np.uint8)
    window.capture_manager.get_active_device = lambda: DummyDevice(frame)
    # Before update, pixmap may be None
    initial_pix = window.preview_label.pixmap()
    # Initial pixmap may be a null pixmap
    assert initial_pix is None or initial_pix.isNull()
    # Call update_preview
    window.update_preview()
    pix = window.preview_label.pixmap()
    assert isinstance(pix, QPixmap)
    # Pixmap dimensions should be non-zero
    size = pix.size()
    assert size.width() > 0 and size.height() > 0


def test_update_preview_failure(window):
    # Simulate get_frame raising
    class BadDevice:
        def get_frame(self): raise RuntimeError("fail capture")
    window.capture_manager.get_active_device = lambda: BadDevice()
    # Should not raise
    try:
        window.update_preview()
    except Exception:
        pytest.fail("update_preview raised exception on failure")
    # Pixmap stays None or unchanged
    final_pix = window.preview_label.pixmap()
    assert final_pix is None or final_pix.isNull()
