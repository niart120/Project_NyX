"""GUI テスト用 conftest."""

import pytest


@pytest.fixture(autouse=True)
def _no_real_hardware(monkeypatch):
    """GUI テストで実デバイス検出を防止する。"""

    class FakeDiscovery:
        def detect(self, timeout_sec=2.0):
            return self

        def serial_names(self):
            return []

        def capture_names(self):
            return []

        def detect_window_sources(self, timeout_sec=2.0):
            return ()

        def find_serial(self, name, timeout_sec):
            return None

        def find_capture(self, name, timeout_sec):
            return None

    monkeypatch.setattr(
        "nyxpy.gui.app_services.DeviceDiscoveryService", lambda **_: FakeDiscovery()
    )
