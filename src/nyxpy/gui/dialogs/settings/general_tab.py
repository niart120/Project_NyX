from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

class GeneralSettingsTab(QWidget):
    def __init__(self, settings:GlobalSettings, secrets:SecretsSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("一般設定項目（今後拡張予定）"))

    def apply(self):
        pass
