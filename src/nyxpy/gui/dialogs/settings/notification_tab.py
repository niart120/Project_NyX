"""通知設定 tab。"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings


class NotificationSettingsTab(QWidget):
    """Discord と Bluesky の通知設定 tab。"""

    def __init__(self, settings: GlobalSettings, secrets: SecretsSettings, parent=None):
        """Global settings と secret store を保持し、通知設定 UI を作ります。"""
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        layout = QVBoxLayout(self)

        # Discord設定
        discord_group = QGroupBox("Discord通知設定")
        discord_form = QFormLayout()
        self.discord_enable = QCheckBox("Discord通知を有効化")
        self.discord_enable.setChecked(self.secrets.get("notification.discord.enabled", False))
        self.discord_url = QLineEdit()
        self.discord_url.setEchoMode(QLineEdit.EchoMode.Password)
        self.discord_url.setText(self.secrets.get("notification.discord.webhook_url", ""))
        discord_form.addRow(self.discord_enable)
        discord_form.addRow("Discord Webhook URL:", self.discord_url)
        discord_group.setLayout(discord_form)
        layout.addWidget(discord_group)

        # Bluesky設定（ユーザーIDとパスワードを使用）
        bluesky_group = QGroupBox("Bluesky通知設定")
        bluesky_form = QFormLayout()
        self.bluesky_enable = QCheckBox("Bluesky通知を有効化")
        self.bluesky_enable.setChecked(self.secrets.get("notification.bluesky.enabled", False))

        self.bluesky_identifier = QLineEdit()
        self.bluesky_identifier.setText(self.secrets.get("notification.bluesky.identifier", ""))

        self.bluesky_password = QLineEdit()
        self.bluesky_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.bluesky_password.setText(self.secrets.get("notification.bluesky.password", ""))

        bluesky_form.addRow(self.bluesky_enable)
        bluesky_form.addRow("Bluesky ユーザーID:", self.bluesky_identifier)
        bluesky_form.addRow("Bluesky パスワード:", self.bluesky_password)
        bluesky_group.setLayout(bluesky_form)
        layout.addWidget(bluesky_group)

        log_group = QGroupBox("ログ", self)
        log_layout = QVBoxLayout(log_group)
        log_form = QFormLayout()
        self.file_level = QComboBox(self)
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.file_level.addItem(level, level)
        self.file_level.setCurrentIndex(
            self.file_level.findData(self.settings.get("logging.file_level", "DEBUG"))
        )
        log_form.addRow(QLabel("ログファイルレベル:"), self.file_level)

        self.command_debug_enabled = QCheckBox("コマンド詳細DEBUGログを出力する", self)
        self.command_debug_enabled.setChecked(
            bool(self.settings.get("logging.command_debug_enabled", False))
        )
        log_form.addRow(QLabel("コマンド詳細ログ:"), self.command_debug_enabled)
        log_layout.addLayout(log_form)
        layout.addWidget(log_group)

        # 余白を埋めるためのスペーサー
        layout.addStretch()

    def apply(self):
        # Discord設定の保存
        self.secrets.set("notification.discord.enabled", self.discord_enable.isChecked())
        self.secrets.set("notification.discord.webhook_url", self.discord_url.text())

        # Bluesky設定の保存
        self.secrets.set("notification.bluesky.enabled", self.bluesky_enable.isChecked())
        self.secrets.set("notification.bluesky.identifier", self.bluesky_identifier.text())
        self.secrets.set("notification.bluesky.password", self.bluesky_password.text())
        self.settings.set("logging.file_level", self.file_level.currentData())
        self.settings.set("logging.command_debug_enabled", self.command_debug_enabled.isChecked())
