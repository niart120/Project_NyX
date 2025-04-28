import pytest
import numpy as np
from unittest.mock import patch
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
        def __init__(self):
            self.macros = {"Dummy": DummyMacro()}

    monkeypatch.setattr("nyxpy.gui.main_window.MacroExecutor", DummyExecutor)
    yield tmp_path


@pytest.fixture
def patched_managers():
    # キャプチャマネージャとシリアルマネージャの非同期動作をパッチ
    with patch("nyxpy.framework.core.hardware.capture.CaptureManager") as mock_cap_mgr:
        with patch(
            "nyxpy.framework.core.hardware.serial_comm.SerialManager"
        ) as mock_ser_mgr:
            # 同期的にデバイスを検出するように振る舞いを変更
            mock_cap_mgr.return_value.auto_register_devices.side_effect = lambda: None
            mock_ser_mgr.return_value.auto_register_devices.side_effect = lambda: None
            yield mock_cap_mgr, mock_ser_mgr


@pytest.fixture
def window(qtbot, tmp_cwd_and_dummy, patched_managers):
    mock_cap_mgr, mock_ser_mgr = patched_managers

    # モックのキャプチャマネージャを設定
    mock_cap_mgr.return_value.list_devices.return_value = ["ダミーデバイス"]

    QApplication.instance() or QApplication([])
    w = MainWindow()
    qtbot.addWidget(w)

    # MainWindowの初期化後に非同期初期化を完了させる
    w.deferred_init()

    # 重要: ウィンドウを明示的に表示する
    w.show()

    # 非推奨の waitForWindowShown の代わりに waitExposed を使用
    # (コンテキストマネージャとして使用)
    with qtbot.waitExposed(w):
        pass

    return w


def test_update_preview_success(window: MainWindow, qtbot):
    # ウィンドウが表示されていることを確認
    assert window.isVisible()

    # プレビューペインが存在することを確認
    assert window.preview_pane is not None

    # プレビューペインが表示されていない場合は明示的に表示
    if not window.preview_pane.isVisible():
        window.preview_pane.setVisible(True)
        qtbot.wait(100)  # GUIの更新を待つ

    # Prepare dummy frame 100x160x3 (より大きなサイズを使用)
    frame = np.full((100, 160, 3), 128, dtype=np.uint8)
    class DummyDevice:
        def get_frame(self):
            return frame
    # 新設計: PreviewPaneに直接デバイスを注入
    window.preview_pane.set_capture_device(DummyDevice())

    # 初期状態ではピクスマップがないかもしれないが、正常に動作させるための処理
    window.preview_pane.label.resize(320, 180)
    window.preview_pane.resize(320, 180)

    # 明示的にレイアウトを更新
    window.preview_pane.layout().activate()
    qtbot.wait(100)
    window.preview_pane.update_preview()
    qtbot.wait(100)

    # 結果確認: ピクスマップが作成されているか
    pix = window.preview_pane.label.pixmap()
    assert pix is not None, "Pixmap should not be None"
    assert isinstance(pix, QPixmap), "Should be a QPixmap instance"
    assert not pix.isNull(), "Pixmap should not be null"


def test_update_preview_failure(window: MainWindow, qtbot):
    # ウィンドウが表示されていることを確認
    assert window.isVisible()

    # プレビューペインが表示されていない場合は明示的に表示
    if not window.preview_pane.isVisible():
        window.preview_pane.setVisible(True)
        qtbot.wait(100)  # GUIの更新を待つ

    # Simulate get_frame raising
    class BadDevice:
        def get_frame(self):
            raise RuntimeError("fail capture")
    # 新設計: PreviewPaneに直接デバイスを注入
    window.preview_pane.set_capture_device(BadDevice())
    try:
        window.preview_pane.update_preview()
    except Exception:
        pytest.fail("update_preview raised exception on failure")
    qtbot.wait(100)
    # Pixmap stays None or unchanged
    final_pix = window.preview_pane.label.pixmap()
    assert final_pix is None or final_pix.isNull()
