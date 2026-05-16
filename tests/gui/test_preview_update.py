from unittest.mock import patch

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap

from nyxpy.framework.core.constants import ScreenPoint
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


def test_preview_keeps_fixed_16_9_size_for_preset(qtbot, tmp_cwd):
    pane = PreviewPane(fixed_preview_size=(640, 360))
    qtbot.addWidget(pane)

    assert pane.label.minimumWidth() == 640
    assert pane.label.maximumWidth() == 640
    assert pane.label.minimumHeight() == 360
    assert pane.label.maximumHeight() == 360

    pane.set_fixed_preview_size(1600, 900)

    assert pane.label.maximumWidth() == 1600
    assert pane.label.maximumHeight() == 900
    pane.timer.stop()


def test_preview_scales_frame_to_fixed_size_without_crop(qtbot, tmp_cwd):
    pane = PreviewPane(fixed_preview_size=(640, 360))
    qtbot.addWidget(pane)
    pane.show()

    class SmallFrameSource:
        def try_latest_frame(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

    pane.set_frame_source(SmallFrameSource())
    target_w = int(640 * pane.devicePixelRatio())
    target_h = int(360 * pane.devicePixelRatio())

    def fake_resize(frame, target_size, *, interpolation):
        return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

    with patch("nyxpy.gui.panes.preview_pane.cv2.resize", side_effect=fake_resize) as resize:
        pane.update_preview()

    assert resize.call_args.args[1] == (target_w, target_h)
    assert resize.call_args.kwargs["interpolation"] == cv2.INTER_LINEAR
    pane.timer.stop()


def test_preview_maps_widget_point_to_hd_capture_point(qtbot, tmp_cwd):
    pane = PreviewPane(fixed_preview_size=(640, 360))
    qtbot.addWidget(pane)

    assert pane.preview_widget_point_to_hd_capture_point(QPoint(200, 180)) == ScreenPoint(400, 360)

    pane.timer.stop()


def test_preview_touch_ignores_pillarbox_press(qtbot, tmp_cwd):
    pane = PreviewPane(fixed_preview_size=(640, 360))
    qtbot.addWidget(pane)
    events = []
    pane.touch_down_requested.connect(lambda x, y: events.append((x, y)))

    qtbot.mousePress(pane.label, Qt.MouseButton.LeftButton, pos=QPoint(199, 180))

    assert events == []
    pane.timer.stop()


def test_preview_touch_emits_press_move_release_inside_bottom_screen(qtbot, tmp_cwd):
    pane = PreviewPane(fixed_preview_size=(640, 360))
    qtbot.addWidget(pane)
    events = []
    pane.touch_down_requested.connect(lambda x, y: events.append(("down", x, y)))
    pane.touch_move_requested.connect(lambda x, y: events.append(("move", x, y)))
    pane.touch_up_requested.connect(lambda: events.append(("up",)))

    qtbot.mousePress(pane.label, Qt.MouseButton.LeftButton, pos=QPoint(200, 180))
    qtbot.mouseMove(pane.label, pos=QPoint(439, 359))
    qtbot.mouseRelease(pane.label, Qt.MouseButton.LeftButton, pos=QPoint(639, 359))

    assert events == [("down", 0, 0), ("move", 319, 239), ("up",)]
    pane.timer.stop()
