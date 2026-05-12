import numpy as np
import pytest
from PySide6.QtGui import QPixmap

from nyxpy.gui.panes.preview_pane import PreviewPane


@pytest.fixture
def tmp_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture
def preview_pane(qtbot, tmp_cwd):
    pane = PreviewPane()
    qtbot.addWidget(pane)
    pane.show()

    with qtbot.waitExposed(pane):
        pass

    yield pane

    pane.timer.stop()


def test_update_preview_success(preview_pane: PreviewPane, qtbot):
    assert preview_pane.isVisible()

    if not preview_pane.isVisible():
        preview_pane.setVisible(True)
        qtbot.wait(100)  # GUIの更新を待つ

    frame = np.full((100, 160, 3), 128, dtype=np.uint8)

    class DummyDevice:
        def get_frame(self):
            return frame

    preview_pane.set_capture_device(DummyDevice())

    preview_pane.label.resize(320, 180)
    preview_pane.resize(320, 180)

    preview_pane.layout().activate()
    qtbot.wait(100)
    preview_pane.update_preview()
    qtbot.wait(100)

    pix = preview_pane.label.pixmap()
    assert pix is not None, "Pixmap should not be None"
    assert isinstance(pix, QPixmap), "Should be a QPixmap instance"
    assert not pix.isNull(), "Pixmap should not be null"


def test_update_preview_failure(preview_pane: PreviewPane, qtbot):
    assert preview_pane.isVisible()

    if not preview_pane.isVisible():
        preview_pane.setVisible(True)
        qtbot.wait(100)  # GUIの更新を待つ

    class BadDevice:
        def get_frame(self):
            raise RuntimeError("fail capture")

    preview_pane.set_capture_device(BadDevice())
    before_pix = preview_pane.label.pixmap()
    try:
        preview_pane.update_preview()
    except Exception:
        pytest.fail("update_preview raised exception on failure")
    qtbot.wait(100)
    after_pix = preview_pane.label.pixmap()
    if after_pix is None or after_pix.isNull():
        pass  # 失敗後にPixmapがクリアされるのは許容
    else:
        before_key = before_pix.cacheKey() if (before_pix and not before_pix.isNull()) else 0
        assert after_pix.cacheKey() == before_key
