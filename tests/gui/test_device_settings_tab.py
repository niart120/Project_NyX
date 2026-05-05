from nyxpy.gui.dialogs.settings.device_tab import DeviceSettingsTab


class FakeSettings:
    def __init__(self):
        self.data = {
            "capture_device": "Camera1",
            "preview_fps": 60,
            "serial_device": "COM1",
            "serial_protocol": "CH552",
            "serial_baud": 9600,
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeManager:
    def __init__(self, devices):
        self.devices = devices

    def list_devices(self):
        return self.devices


def test_device_tab_protocol_options_include_3ds(monkeypatch, qtbot):
    monkeypatch.setattr(
        "nyxpy.gui.dialogs.settings.device_tab.capture_manager",
        FakeManager(["Camera1"]),
    )
    monkeypatch.setattr(
        "nyxpy.gui.dialogs.settings.device_tab.serial_manager",
        FakeManager(["COM1"]),
    )

    tab = DeviceSettingsTab(FakeSettings(), None)
    qtbot.addWidget(tab)

    options = [tab.ser_protocol.itemText(i) for i in range(tab.ser_protocol.count())]
    assert "3DS" in options


def test_device_tab_selects_3ds_default_baudrate(monkeypatch, qtbot):
    monkeypatch.setattr(
        "nyxpy.gui.dialogs.settings.device_tab.capture_manager",
        FakeManager(["Camera1"]),
    )
    monkeypatch.setattr(
        "nyxpy.gui.dialogs.settings.device_tab.serial_manager",
        FakeManager(["COM1"]),
    )

    tab = DeviceSettingsTab(FakeSettings(), None)
    qtbot.addWidget(tab)

    tab.ser_protocol.setCurrentText("3DS")

    assert tab.ser_baud.currentText() == "115200"
