import numpy as np
import pytest
from PySide6.QtGui import QPixmap

from nyxpy.gui.main_window import MainWindow


@pytest.fixture
def tmp_cwd_and_dummy(monkeypatch, tmp_path):
    # isolate cwd and patch macro catalog
    monkeypatch.chdir(tmp_path)

    class DummyMacro:
        description = ""
        tags = []

    class DummyCatalog:
        def __init__(self, registry):
            self.macros = {"Dummy": DummyMacro()}

    monkeypatch.setattr("nyxpy.gui.main_window.MacroCatalog", DummyCatalog)
    yield tmp_path


@pytest.fixture
def window(qtbot, tmp_cwd_and_dummy):
    # conftest の _no_real_hardware で initialize_managers は no-op 化済み
    w = MainWindow()
    qtbot.addWidget(w)

    # MainWindowの初期化後に非同期初期化を完了させる
    w.deferred_init()

    # 重要: ウィンドウを明示的に表示する
    w.show()

    # 非推奨の waitForWindowShown の代わりに waitExposed を使用
    with qtbot.waitExposed(w):
        pass

    yield w

    # teardown: プレビュータイマーを確実に停止
    w.preview_pane.timer.stop()


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
    # 失敗前のPixmapを保存
    before_pix = window.preview_pane.label.pixmap()
    try:
        window.preview_pane.update_preview()
    except Exception:
        pytest.fail("update_preview raised exception on failure")
    qtbot.wait(100)
    # 失敗後のPixmap
    after_pix = window.preview_pane.label.pixmap()
    # PixmapがNone・null、または変更されていないことを確認
    if after_pix is None or after_pix.isNull():
        pass  # 失敗後にPixmapがクリアされるのは許容
    else:
        before_key = before_pix.cacheKey() if (before_pix and not before_pix.isNull()) else 0
        assert after_pix.cacheKey() == before_key
