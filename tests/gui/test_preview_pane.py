import pytest
import os
import sys
import numpy as np
import cv2
from unittest.mock import Mock, patch
from pathlib import Path
from PySide6.QtWidgets import QApplication
from nyxpy.gui.panes.preview_pane import PreviewPane, SNAPSHOT_DIR

# Add the project root to sys.path if needed
sys.path.append(str(Path(__file__).parents[4]))


@pytest.fixture
def app():
    """Create QApplication instance for tests."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def preview_pane(app):
    """Create a PreviewPane with mocked dependencies."""
    # Mock capture device
    device_mock = Mock()
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    device_mock.get_frame.return_value = test_frame
    # cv2モジュールをパッチして初期化中の例外を防ぐ
    with patch("nyxpy.gui.panes.preview_pane.cv2") as mock_cv2:
        mock_cv2.resize.return_value = test_frame
        mock_cv2.INTER_LINEAR = cv2.INTER_LINEAR
        pane = PreviewPane(capture_device=device_mock, capture_fps=30)
    return pane


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
        mock_cv2.resize.assert_called_once_with(
            test_frame, (1280, 720), interpolation=mock_cv2.INTER_AREA
        )
        mock_cv2.imwrite.assert_called_once_with(str(expected_path), test_frame)
        signal_mock.emit.assert_called_once_with(
            f"スナップショット保存: {mock_timestamp}.png"
        )
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
