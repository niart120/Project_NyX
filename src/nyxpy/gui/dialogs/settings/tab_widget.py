"""設定 dialog の tab container。"""

from collections.abc import Callable

from PySide6.QtWidgets import QTabWidget

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

from .device_tab import DeviceSettingsTab
from .notification_tab import NotificationSettingsTab


class SettingsTabWidget(QTabWidget):
    """Application settings dialog 内の設定 tab container。"""

    def __init__(
        self,
        parent,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
        ponkan_capture_available: bool | None = None,
        swbt_adapter_provider: Callable[[], tuple[SwbtAdapterView, ...]] | None = None,
        swbt_pair: Callable[[], object] | None = None,
        swbt_reconnect: Callable[[], object] | None = None,
        swbt_disconnect: Callable[[], None] | None = None,
        swbt_status: Callable[[], object | None] | None = None,
        swbt_actions_enabled: bool = True,
    ):
        """Device/notification tab を生成し、store と discovery service を渡します。"""
        super().__init__(parent)
        self.device_tab = DeviceSettingsTab(
            settings,
            secrets,
            device_discovery=device_discovery,
            ponkan_capture_available=ponkan_capture_available,
            swbt_adapter_provider=swbt_adapter_provider,
            swbt_pair=swbt_pair,
            swbt_reconnect=swbt_reconnect,
            swbt_disconnect=swbt_disconnect,
            swbt_status=swbt_status,
            swbt_actions_enabled=swbt_actions_enabled,
        )
        self.notification_tab = NotificationSettingsTab(settings, secrets)

        self.addTab(self.device_tab, "一般")
        self.addTab(self.notification_tab, "通知・ログ")
