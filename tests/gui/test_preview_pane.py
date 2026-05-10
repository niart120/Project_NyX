import os
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

from nyxpy.gui.panes.preview_pane import SNAPSHOT_DIR, PreviewPane


@pytest.fixture
def preview_pane(qtbot):
    """Create a PreviewPane with mocked dependencies."""
    # Mock capture device
    device_mock = Mock()
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    device_mock.get_frame.return_value = test_frame
    # cv2モジュールをパッチして初期化中の例外を防ぐ
    with patch("nyxpy.gui.panes.preview_pane.cv2") as mock_cv2:
        mock_cv2.resize.return_value = test_frame
        mock_cv2.INTER_LINEAR = cv2.INTER_LINEAR
        pane = PreviewPane(
            capture_device=device_mock,
            preview_fps=20,  # プレビュー用のみ
        )
    qtbot.addWidget(pane)
    yield pane
    # teardown: タイマーを確実に停止
    pane.timer.stop()


class TestPreviewPane:
    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_success(
        self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path
    ):
        """Test successful snapshot taking."""
        monkeypatch.chdir(tmp_path)
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        preview_pane.capture_device.get_frame.return_value = test_frame
        mock_cv2.resize.return_value = test_frame
        mock_cv2.imwrite.return_value = True
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        result = preview_pane.take_snapshot()
        expected_path = Path.cwd() / SNAPSHOT_DIR / f"{mock_timestamp}.png"
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        resized_frame, target_size = mock_cv2.resize.call_args.args
        assert np.array_equal(resized_frame, test_frame)
        assert target_size == (1280, 720)
        assert mock_cv2.resize.call_args.kwargs == {"interpolation": mock_cv2.INTER_AREA}
        mock_cv2.imwrite.assert_called_once_with(str(expected_path), test_frame)
        signal_mock.emit.assert_called_once_with(f"スナップショット保存: {mock_timestamp}.png")
        assert result == f"スナップショット保存: {mock_timestamp}.png"

    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_no_frame(
        self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path
    ):
        """Test snapshot taking when frame is None."""
        monkeypatch.chdir(tmp_path)
        preview_pane.capture_device.get_frame.return_value = None
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        mock_cv2.resize.side_effect = Exception("Cannot resize None")
        result = preview_pane.take_snapshot()
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        assert not mock_cv2.imwrite.called
        assert result == "プレビューがありません。スナップショットに失敗しました。"
        signal_mock.emit.assert_called_once_with(
            "プレビューがありません。スナップショットに失敗しました。"
        )

    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_write_failure(
        self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path
    ):
        """Test snapshot taking when write fails."""
        monkeypatch.chdir(tmp_path)
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        preview_pane.capture_device.get_frame.return_value = test_frame
        mock_cv2.resize.return_value = test_frame
        mock_cv2.imwrite.return_value = False
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        result = preview_pane.take_snapshot()
        expected_path = Path.cwd() / SNAPSHOT_DIR / f"{mock_timestamp}.png"
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        mock_cv2.imwrite.assert_called_once_with(str(expected_path), test_frame)
        expected_msg = f"スナップショット保存: {mock_timestamp}.png"
        signal_mock.emit.assert_called_once_with(expected_msg)
        assert result == expected_msg

    def test_update_preview_skips_when_frame_source_busy(self, preview_pane, qtbot):
        """Busy FrameSourcePort should keep the current pixmap and not block the UI."""
        frame_source = Mock()
        frame_source.try_latest_frame.return_value = None
        preview_pane.set_frame_source(frame_source)
        preview_pane.show()
        qtbot.wait(10)
        before_pixmap = preview_pane.label.pixmap()
        before_key = before_pixmap.cacheKey() if before_pixmap is not None else None

        preview_pane.update_preview()

        after_pixmap = preview_pane.label.pixmap()
        after_key = after_pixmap.cacheKey() if after_pixmap is not None else None
        assert after_key == before_key
        frame_source.try_latest_frame.assert_called()
