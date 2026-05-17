from nyxpy.framework.core.hardware.device_discovery import DeviceInfo
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.dialogs.settings.notification_tab import NotificationSettingsTab
from nyxpy.gui.dialogs.settings.tab_widget import SettingsTabWidget


class FakeSettings:
    def __init__(self) -> None:
        self.data = {
            "logging.file_level": "INFO",
            "logging.command_debug_enabled": False,
            "gui.window_size_preset": "full_hd",
            "capture_source_type": "camera",
            "capture_device": "",
            "serial_device": "",
            "serial_protocol": "CH552",
            "serial_baud": 9600,
            "preview_fps": 60,
        }

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value


class FakeSecrets:
    def __init__(self) -> None:
        self.data = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value


class FakeDiscovery:
    def detect(self, timeout_sec=2.0):
        return self

    @property
    def serial_devices(self):
        return (DeviceInfo(kind="serial", name="USB Serial Device (COM1)", identifier="COM1"),)

    def capture_names(self):
        return []

    def detect_window_sources(self, timeout_sec=2.0):
        return ()


def test_settings_tabs_are_general_and_notification_log(qtbot) -> None:
    tabs = SettingsTabWidget(
        None,
        FakeSettings(),
        FakeSecrets(),
        device_discovery=FakeDiscovery(),
    )
    qtbot.addWidget(tabs)

    assert tabs.count() == 2
    assert tabs.tabText(0) == "一般"
    assert tabs.tabText(1) == "通知・ログ"


def test_settings_dialog_title_is_settings(qtbot) -> None:
    dialog = AppSettingsDialog(
        None,
        FakeSettings(),
        FakeSecrets(),
        device_discovery=FakeDiscovery(),
    )
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "設定"


def test_notification_log_tab_applies_logging_settings(qtbot) -> None:
    settings = FakeSettings()
    tab = NotificationSettingsTab(settings, FakeSecrets())
    qtbot.addWidget(tab)

    tab.file_level.setCurrentIndex(tab.file_level.findData("ERROR"))
    tab.command_debug_enabled.setChecked(True)
    tab.apply()

    assert settings.data["logging.file_level"] == "ERROR"
    assert settings.data["logging.command_debug_enabled"] is True
