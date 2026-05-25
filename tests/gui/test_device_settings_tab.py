from PySide6.QtWidgets import QLabel

from nyxpy.framework.core.hardware.capture_source import CaptureRect
from nyxpy.framework.core.hardware.device_discovery import DeviceInfo
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
            "capture_fps": None,
            "capture_aspect_box_enabled": False,
            "preview_fps": 60,
            "serial_device": "COM1",
            "serial_protocol": "CH552",
            "serial_baud": 9600,
            "gui.window_size_preset": "full_hd",
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class FakeDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    @property
    def serial_devices(self):
        return (DeviceInfo(kind="serial", name="USB Serial Device (COM1)", identifier="COM1"),)

    def capture_names(self):
        return ["Camera1"]

    def serial_names(self):
        return ["COM1"]

    def detect_window_sources(self, timeout_sec=2.0):
        return (WindowInfo("Viewer", "hwnd-1", CaptureRect(10, 20, 600, 720)),)


class EmptyDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    @property
    def serial_devices(self):
        return ()

    def capture_names(self):
        return []

    def detect_window_sources(self, timeout_sec=2.0):
        return ()


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


def test_device_settings_tab_places_letterbox_on_source_row(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert tab.aspect_box_enabled.parent() is tab.source_row
    assert "Aspect Box:" not in _label_texts(tab.cap_group)

    tab.aspect_box_enabled.setChecked(True)
    tab.apply()

    assert settings.data["capture_aspect_box_enabled"] is True


def test_device_settings_tab_hides_irrelevant_source_fields(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert not tab.cap_device.isHidden()
    assert tab.window_row.isHidden()

    tab.capture_source_type.setCurrentText("window")
    assert tab.camera_row.isHidden()
    assert not tab.window_row.isHidden()
    assert not tab.window_match_mode.isHidden()
    assert not tab.capture_backend.isHidden()

    tab.capture_source_type.setCurrentText("camera")
    assert not tab.cap_device.isHidden()
    assert tab.window_row.isHidden()


def test_device_settings_tab_saves_serial_identifier(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert tab.ser_device.currentText() == "USB Serial Device (COM1)"
    tab.apply()

    assert settings.data["serial_device"] == "COM1"


def test_device_settings_tab_does_not_list_stale_serial_setting(qtbot):
    settings = FakeSettings()
    settings.data["serial_device"] = "COM9"
    tab = DeviceSettingsTab(settings, None, device_discovery=EmptyDiscovery())
    qtbot.addWidget(tab)

    assert tab.ser_device.findText("COM9") < 0
    assert tab.ser_device.count() == 0


def test_device_settings_tab_does_not_list_stale_window_setting(qtbot):
    settings = FakeSettings()
    settings.data["capture_window_title"] = "Disconnected Viewer"
    settings.data["capture_window_identifier"] = "hwnd-old"
    tab = DeviceSettingsTab(settings, None, device_discovery=EmptyDiscovery())
    qtbot.addWidget(tab)

    assert tab.window_source.findText("Disconnected Viewer") < 0
    assert tab.window_source.count() == 0


def test_device_settings_tab_updates_window_size_preset(qtbot):
    settings = FakeSettings()
    tab = DeviceSettingsTab(settings, None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    tab.window_size_preset.setCurrentIndex(tab.window_size_preset.findData("four_k"))
    tab.apply()

    assert settings.data["gui.window_size_preset"] == "four_k"


def test_device_settings_tab_places_preview_fps_in_appearance_group(qtbot):
    tab = DeviceSettingsTab(FakeSettings(), None, device_discovery=FakeDiscovery())
    qtbot.addWidget(tab)

    assert "Preview FPS:" not in _label_texts(tab.cap_group)
    assert "Preview FPS:" in _label_texts(tab.appearance_group)


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]
