"""GUI テスト用 conftest."""

import pytest

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryResult


@pytest.fixture(autouse=True)
def _no_real_hardware(monkeypatch):
    """GUI テストで実デバイス検出を防止する。"""

    class FakeDiscovery:
        @property
        def last_result(self):
            return DeviceDiscoveryResult()

        def detect(self, timeout_sec=2.0):
            return self.last_result

        def serial_names(self):
            return []

        def capture_names(self):
            return []

        def detect_window_sources(self, timeout_sec=2.0):
            return ()

    monkeypatch.setattr(
        "nyxpy.gui.app_services.DeviceDiscoveryService", lambda **_: FakeDiscovery()
    )
