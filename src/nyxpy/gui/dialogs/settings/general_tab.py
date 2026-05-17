from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.gui.layout import WINDOW_SIZE_PRESETS, normalize_window_size_preset_key


class GeneralSettingsTab(QWidget):
    def __init__(self, settings: GlobalSettings, secrets: SecretsSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        layout = QVBoxLayout(self)

        appearance_group = QGroupBox("外観", self)
        appearance_layout = QVBoxLayout(appearance_group)
        appearance_form = QFormLayout()
        self.window_size_preset = QComboBox(self)
        for preset in WINDOW_SIZE_PRESETS:
            self.window_size_preset.addItem(preset.label, preset.key)
        current_key = normalize_window_size_preset_key(
            self.settings.get("gui.window_size_preset", "full_hd")
        )
        self.window_size_preset.setCurrentIndex(self.window_size_preset.findData(current_key))
        appearance_form.addRow(QLabel("ウィンドウサイズ:"), self.window_size_preset)
        appearance_layout.addLayout(appearance_form)
        layout.addWidget(appearance_group)

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
        layout.addStretch(1)

    def apply(self):
        self.settings.set("gui.window_size_preset", self.window_size_preset.currentData())
        self.settings.set("logging.file_level", self.file_level.currentData())
        self.settings.set("logging.command_debug_enabled", self.command_debug_enabled.isChecked())
