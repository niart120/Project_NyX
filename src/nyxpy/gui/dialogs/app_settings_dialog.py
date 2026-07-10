"""GUI の application settings dialog。"""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

from .settings.device_tab import SwbtLifecycleAction
from .settings.tab_widget import SettingsTabWidget


class AppSettingsDialog(QDialog):
    """Global/secret settings を tab 形式で編集する dialog。"""

    settings_applied = Signal()

    def __init__(
        self,
        parent,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
        ponkan_capture_available: bool | None = None,
        swbt_adapter_provider: Callable[[], tuple[SwbtAdapterView, ...]] | None = None,
        swbt_pair: SwbtLifecycleAction | None = None,
        swbt_reconnect: SwbtLifecycleAction | None = None,
        swbt_disconnect: SwbtLifecycleAction | None = None,
        swbt_status: Callable[[], object | None] | None = None,
        swbt_actions_enabled: bool = True,
    ):
        """Settings tab を構築し、適用ボタンの signal を接続します。"""
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.resize(500, 400)
        self.settings = settings
        self.secrets = secrets
        layout = QVBoxLayout(self)

        # タブウィジェット
        self.tab_widget = SettingsTabWidget(
            self,
            self.settings,
            self.secrets,
            device_discovery=device_discovery,
            ponkan_capture_available=ponkan_capture_available,
            swbt_adapter_provider=swbt_adapter_provider,
            swbt_pair=swbt_pair,
            swbt_reconnect=swbt_reconnect,
            swbt_disconnect=swbt_disconnect,
            swbt_status=swbt_status,
            swbt_actions_enabled=swbt_actions_enabled,
        )
        layout.addWidget(self.tab_widget)

        # ボタンレイアウト
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("適用")
        apply_btn.clicked.connect(self.apply_settings)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

    def apply_settings(self):
        if self.tab_widget.device_tab.swbt_lifecycle_busy:
            self.tab_widget.device_tab.swbt_status_label.setText(
                "接続操作の完了後に設定を反映してください"
            )
            return False
        self.tab_widget.device_tab.apply()
        self.tab_widget.notification_tab.apply()
        self.settings_applied.emit()
        return True

    def accept(self):
        if not self.apply_settings():
            return
        super().accept()
