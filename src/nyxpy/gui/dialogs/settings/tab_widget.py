from PySide6.QtWidgets import QTabWidget
from .general_tab import GeneralSettingsTab
from .device_tab import DeviceSettingsTab
from .notification_tab import NotificationSettingsTab

class SettingsTabWidget(QTabWidget):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        # 各タブを個別のQWidgetサブクラスとして分離
        self.general_tab = GeneralSettingsTab(settings)
        self.device_tab = DeviceSettingsTab(settings)
        self.notification_tab = NotificationSettingsTab(settings)
        self.addTab(self.general_tab, "一般")
        self.addTab(self.device_tab, "デバイス")
        self.addTab(self.notification_tab, "通知")
