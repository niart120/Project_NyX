from nyxpy.framework.core.hardware.capture_source import CaptureRect
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.gui.dialogs.settings.device_tab import DeviceSettingsTab


class FakeSettings:
    def __init__(self):
        self.data = {
            "capture_device": "Camera1",
            "capture_source_type": "camera",
            "capture_window_title": "",
            "capture_window_match_mode": "exact",
            "capture_window_identifier": "",
            "capture_backend": "auto",
            "capture_region": {},
            "capture_fps": None,
            "capture_aspect_box_enabled": False,
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

    def detect_window_sources(self, timeout_sec=2.0):
        return (WindowInfo("Viewer", "hwnd-1", CaptureRect(10, 20, 600, 720)),)


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


def test_device_settings_tab_shows_capture_source_type(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert [
        tab.capture_source_type.itemText(i) for i in range(tab.capture_source_type.count())
    ] == [
        "camera",
        "window",
        "screen_region",
    ]


def test_device_settings_tab_applies_window_capture_settings(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.capture_source_type.setCurrentText("window")
    tab.window_source.setCurrentIndex(0)
    tab.window_match_mode.setCurrentText("contains")
    tab.capture_backend.setCurrentText("mss")
    tab.apply()

    assert settings.data["capture_source_type"] == "window"
    assert settings.data["capture_window_title"] == "Viewer"
    assert settings.data["capture_window_identifier"] == "hwnd-1"
    assert settings.data["capture_window_match_mode"] == "contains"
    assert settings.data["capture_backend"] == "mss"


def test_device_settings_tab_uses_framework_window_candidates_in_combo(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    data = tab.window_source.itemData(0)

    assert tab.window_source.isEditable()
    assert tab.window_source.itemText(0) == "Viewer"
    assert data == {"title": "Viewer", "identifier": "hwnd-1"}


def test_device_settings_tab_saves_custom_window_title_without_identifier(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.capture_source_type.setCurrentText("window")
    tab.window_source.setEditText("View")
    tab.window_match_mode.setCurrentText("contains")
    tab.apply()

    assert settings.data["capture_window_title"] == "View"
    assert settings.data["capture_window_identifier"] == ""
    assert settings.data["capture_window_match_mode"] == "contains"


def test_device_settings_tab_applies_screen_region_settings(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.capture_source_type.setCurrentText("screen_region")
    tab.region_left.setValue(11)
    tab.region_top.setValue(22)
    tab.region_width.setValue(600)
    tab.region_height.setValue(720)
    tab.apply()

    assert settings.data["capture_region"] == {
        "left": 11,
        "top": 22,
        "width": 600,
        "height": 720,
    }


def test_device_settings_tab_applies_aspect_box_setting(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.aspect_box_enabled.setChecked(True)
    tab.apply()

    assert settings.data["capture_aspect_box_enabled"] is True


def test_device_settings_tab_disables_irrelevant_fields(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.capture_source_type.setCurrentText("window")
    assert not tab.cap_device.isEnabled()
    assert tab.window_source.isEnabled()
    assert not tab.region_width.isEnabled()

    tab.capture_source_type.setCurrentText("screen_region")
    assert not tab.cap_device.isEnabled()
    assert not tab.window_source.isEnabled()
    assert tab.region_width.isEnabled()
