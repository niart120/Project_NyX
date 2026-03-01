"""GUI テスト用 conftest.

すべての GUI テストで実ハードウェアへのアクセスを防止する。
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _no_real_hardware(monkeypatch):
    """initialize_managers を no-op にして実デバイス検出を防止する。

    MainWindow.__init__() が呼ぶ initialize_managers() は、
    CaptureManager/SerialManager のシングルトン上でバックグラウンドスレッドを
    起動し実デバイスを探索する。テストでは不要なため無効化する。
    """
    monkeypatch.setattr(
        "nyxpy.gui.main_window.initialize_managers",
        lambda: None,
    )
