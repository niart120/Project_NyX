from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QCheckBox, QLineEdit
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.secrets_settings import SecretsSettings

class NotificationSettingsTab(QWidget):
    def __init__(self, settings:GlobalSettings, secrets:SecretsSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        layout = QVBoxLayout(self)
        notify_form = QFormLayout()
        # Discord
        self.discord_enable = QCheckBox("Discord通知を有効化")
        self.discord_enable.setChecked(self.settings.get("notification.discord.enabled", False))
        self.discord_url = QLineEdit()
        self.discord_url.setEchoMode(QLineEdit.Password)
        self.discord_url.setText(self.secrets.get("notification.discord.webhook_url", ""))
        notify_form.addRow(self.discord_enable)
        notify_form.addRow("Discord Webhook URL:", self.discord_url)
        # Bluesky
        self.bluesky_enable = QCheckBox("Bluesky通知を有効化")
        self.bluesky_enable.setChecked(self.settings.get("notification.bluesky.enabled", False))
        self.bluesky_url = QLineEdit()
        self.bluesky_url.setEchoMode(QLineEdit.Password)
        self.bluesky_url.setText(self.secrets.get("notification.bluesky.webhook_url", ""))
        notify_form.addRow(self.bluesky_enable)
        notify_form.addRow("Bluesky Webhook URL:", self.bluesky_url)
        layout.addLayout(notify_form)

    def apply(self):
        self.settings.set("notification.discord.enabled", self.discord_enable.isChecked())
        self.secrets.set("notification.discord.webhook_url", self.discord_url.text())
        self.settings.set("notification.bluesky.enabled", self.bluesky_enable.isChecked())
        self.secrets.set("notification.bluesky.webhook_url", self.bluesky_url.text())
