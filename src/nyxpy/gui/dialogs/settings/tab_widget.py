from PySide6.QtWidgets import QTabWidget

from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from .general_tab import GeneralSettingsTab
from .device_tab import DeviceSettingsTab
from .notification_tab import NotificationSettingsTab

class SettingsTabWidget(QTabWidget):
    def __init__(self, parent=None, settings:GlobalSettings=None, secrets:SecretsSettings=None):
        super().__init__(parent)
        self.general_tab = GeneralSettingsTab(settings, secrets)
        self.device_tab = DeviceSettingsTab(settings, secrets)
        self.notification_tab = NotificationSettingsTab(settings, secrets)
        
        # self.addTab(self.general_tab, "一般")  # 一般タブは今後拡張予定
        self.addTab(self.device_tab, "デバイス")
        self.addTab(self.notification_tab, "通知")
