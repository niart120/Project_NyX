from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal
from .settings.tab_widget import SettingsTabWidget
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.secrets_settings import SecretsSettings

class DeviceSettingsDialog(QDialog):
    settings_applied = Signal()

    def __init__(self, parent, settings:GlobalSettings=None, secrets:SecretsSettings=None):
        super().__init__(parent)
        self.setWindowTitle("デバイス・通知・一般設定")
        self.resize(500, 400)
        self.settings = settings or GlobalSettings()
        self.secrets = secrets or SecretsSettings()
        layout = QVBoxLayout(self)

        # タブウィジェット
        self.tab_widget = SettingsTabWidget(self, self.settings, self.secrets)
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
        self.tab_widget.general_tab.apply()
        self.tab_widget.device_tab.apply()
        self.tab_widget.notification_tab.apply()
        self.settings_applied.emit()

    def accept(self):
        self.apply_settings()
        super().accept()
