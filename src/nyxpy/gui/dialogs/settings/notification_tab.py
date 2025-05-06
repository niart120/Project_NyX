from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QCheckBox, QLineEdit, QGroupBox
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

class NotificationSettingsTab(QWidget):
    def __init__(self, settings:GlobalSettings, secrets:SecretsSettings, parent=None):
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
        self.discord_url.setEchoMode(QLineEdit.Password)
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
        self.bluesky_password.setEchoMode(QLineEdit.Password)
        self.bluesky_password.setText(self.secrets.get("notification.bluesky.password", ""))
        
        bluesky_form.addRow(self.bluesky_enable)
        bluesky_form.addRow("Bluesky ユーザーID:", self.bluesky_identifier)
        bluesky_form.addRow("Bluesky パスワード:", self.bluesky_password)
        bluesky_group.setLayout(bluesky_form)
        layout.addWidget(bluesky_group)
        
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
