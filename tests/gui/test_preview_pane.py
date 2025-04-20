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
    # Mock the settings service
    settings_service = Mock()
    settings_service.global_settings = {"capture_aspect_w": 16, "capture_aspect_h": 9, "capture_fps": 30}
    
    # Mock capture manager and device
    device_mock = Mock()
    # デフォルトで有効なnumpy配列を返すように設定
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    device_mock.get_frame.return_value = test_frame
    
    settings_service.capture_manager = Mock()
    settings_service.capture_manager.get_active_device.return_value = device_mock
    settings_service.capture_manager.auto_register_devices.return_value = None
    settings_service.capture_manager.list_devices.return_value = ["device1"]
    settings_service.capture_manager.set_active.return_value = None
    
    # cv2モジュールをパッチして初期化中の例外を防ぐ
    with patch("nyxpy.gui.panes.preview_pane.cv2") as mock_cv2:
        mock_cv2.resize.return_value = test_frame
        mock_cv2.INTER_LINEAR = cv2.INTER_LINEAR
        pane = PreviewPane(settings_service)
    
    return pane


class TestPreviewPane:
    
    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_success(self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path):
        """Test successful snapshot taking."""
        # Setup
        monkeypatch.chdir(tmp_path)
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        preview_pane.capture_manager.get_active_device().get_frame.return_value = test_frame
        mock_cv2.resize.return_value = test_frame
        mock_cv2.imwrite.return_value = True
        
        # Mock datetime
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        
        # Mock signal emission
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        
        # Execute
        result = preview_pane.take_snapshot()
        
        # Verify
        expected_path = Path.cwd() / SNAPSHOT_DIR / f"{mock_timestamp}.png"
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        mock_cv2.resize.assert_called_once_with(test_frame, (1280, 720), interpolation=mock_cv2.INTER_LINEAR)
        mock_cv2.imwrite.assert_called_once_with(str(expected_path), test_frame)
        signal_mock.emit.assert_called_once_with(f"スナップショット保存: {mock_timestamp}.png")
        assert result == f"スナップショット保存: {mock_timestamp}.png"
    
    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_no_frame(self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path):
        """Test snapshot taking when frame is None."""
        # Setup
        monkeypatch.chdir(tmp_path)
        preview_pane.capture_manager.get_active_device().get_frame.return_value = None
        
        # Mock datetime
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        
        # Mock signal emission
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        
        # cv2.resize should raise exception with None input
        mock_cv2.resize.side_effect = Exception("Cannot resize None")
        
        # Execute
        result = preview_pane.take_snapshot()
        
        # Verify
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        assert not mock_cv2.imwrite.called
        assert result == "プレビューがありません。スナップショットに失敗しました。"
        signal_mock.emit.assert_called_once_with("プレビューがありません。スナップショットに失敗しました。")
    
    @patch("nyxpy.gui.panes.preview_pane.cv2")
    @patch("nyxpy.gui.panes.preview_pane.datetime")
    def test_take_snapshot_write_failure(self, mock_datetime, mock_cv2, preview_pane, monkeypatch, tmp_path):
        """Test snapshot taking when write fails."""
        # Setup
        monkeypatch.chdir(tmp_path)
        test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        preview_pane.capture_manager.get_active_device().get_frame.return_value = test_frame
        mock_cv2.resize.return_value = test_frame
        # 現在の実装では、cv2.imwrite()の戻り値をチェックしていないため、
        # 失敗してもスナップショット保存メッセージが返される
        mock_cv2.imwrite.return_value = False
        
        # Mock datetime
        mock_timestamp = "20230101_120000"
        mock_datetime.now.return_value.strftime.return_value = mock_timestamp
        
        # Mock signal emission
        signal_mock = Mock()
        preview_pane.snapshot_taken = signal_mock
        
        # Execute
        result = preview_pane.take_snapshot()
        
        # Verify
        expected_path = Path.cwd() / SNAPSHOT_DIR / f"{mock_timestamp}.png"
        assert os.path.exists(Path.cwd() / SNAPSHOT_DIR)
        mock_cv2.imwrite.assert_called_once_with(str(expected_path), test_frame)
        # 現在の実装では、失敗してもスナップショット保存メッセージが返される
        expected_msg = f"スナップショット保存: {mock_timestamp}.png"
        signal_mock.emit.assert_called_once_with(expected_msg)
        assert result == expected_msg