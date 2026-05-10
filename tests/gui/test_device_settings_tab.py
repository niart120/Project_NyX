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


class FakeDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    def capture_names(self):
        return ["Camera1"]

    def serial_names(self):
        return ["COM1"]


def test_device_tab_protocol_options_include_3ds(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    options = [tab.ser_protocol.itemText(i) for i in range(tab.ser_protocol.count())]
    assert "3DS" in options


def test_device_tab_selects_3ds_default_baudrate(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.ser_protocol.setCurrentText("3DS")

    assert tab.ser_baud.currentText() == "115200"
