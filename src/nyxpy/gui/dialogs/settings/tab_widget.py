"""設定 dialog の tab container。"""

from PySide6.QtWidgets import QTabWidget

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

from .device_tab import DeviceSettingsTab
from .notification_tab import NotificationSettingsTab


class SettingsTabWidget(QTabWidget):
    """Application settings dialog 内の設定 tab container。"""

    def __init__(
        self,
        parent=None,
        settings: GlobalSettings = None,
        secrets: SecretsSettings = None,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
    ):
        """Device/notification tab を生成し、store と discovery service を渡します。"""
        super().__init__(parent)
        self.device_tab = DeviceSettingsTab(
            settings,
            secrets,
            device_discovery=device_discovery,
        )
        self.notification_tab = NotificationSettingsTab(settings, secrets)

        self.addTab(self.device_tab, "一般")
        self.addTab(self.notification_tab, "通知・ログ")
