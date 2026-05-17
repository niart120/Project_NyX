from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QSpinBox,
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
        form = QFormLayout()
        self.window_size_preset = QComboBox(self)
        for preset in WINDOW_SIZE_PRESETS:
            self.window_size_preset.addItem(preset.label, preset.key)
        current_key = normalize_window_size_preset_key(
            self.settings.get("gui.window_size_preset", "full_hd")
        )
        self.window_size_preset.setCurrentIndex(self.window_size_preset.findData(current_key))
        form.addRow(QLabel("ウィンドウサイズ:"), self.window_size_preset)

        self.file_level = QComboBox(self)
        self.gui_level = QComboBox(self)
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.file_level.addItem(level, level)
            self.gui_level.addItem(level, level)
        self.file_level.setCurrentIndex(
            self.file_level.findData(self.settings.get("logging.file_level", "DEBUG"))
        )
        self.gui_level.setCurrentIndex(
            self.gui_level.findData(self.settings.get("logging.gui_level", "INFO"))
        )
        form.addRow(QLabel("ログファイルレベル:"), self.file_level)
        form.addRow(QLabel("GUIログレベル:"), self.gui_level)

        self.file_max_mb = QSpinBox(self)
        self.file_max_mb.setRange(1, 1024)
        self.file_max_mb.setValue(
            max(
                1,
                int(self.settings.get("logging.file_max_bytes", 10 * 1024 * 1024)) // 1024 // 1024,
            )
        )
        form.addRow(QLabel("ログローテーションサイズ(MB):"), self.file_max_mb)

        self.file_backup_count = QSpinBox(self)
        self.file_backup_count.setRange(0, 100)
        self.file_backup_count.setValue(int(self.settings.get("logging.file_backup_count", 3)))
        form.addRow(QLabel("ログバックアップ数:"), self.file_backup_count)

        self.file_retention_days = QSpinBox(self)
        self.file_retention_days.setRange(1, 3650)
        self.file_retention_days.setValue(int(self.settings.get("logging.file_retention_days", 14)))
        form.addRow(QLabel("ログ保持日数:"), self.file_retention_days)

        self.run_retention_days = QSpinBox(self)
        self.run_retention_days.setRange(1, 3650)
        self.run_retention_days.setValue(int(self.settings.get("logging.run_retention_days", 30)))
        form.addRow(QLabel("実行ログ保持日数:"), self.run_retention_days)

        self.command_debug_enabled = QCheckBox("コマンド詳細DEBUGログを出力する", self)
        self.command_debug_enabled.setChecked(
            bool(self.settings.get("logging.command_debug_enabled", False))
        )
        form.addRow(QLabel("コマンド詳細ログ:"), self.command_debug_enabled)
        layout.addLayout(form)

    def apply(self):
        self.settings.set("gui.window_size_preset", self.window_size_preset.currentData())
        self.settings.set("logging.file_level", self.file_level.currentData())
        self.settings.set("logging.gui_level", self.gui_level.currentData())
        self.settings.set("logging.file_max_bytes", self.file_max_mb.value() * 1024 * 1024)
        self.settings.set("logging.file_backup_count", self.file_backup_count.value())
        self.settings.set("logging.file_retention_days", self.file_retention_days.value())
        self.settings.set("logging.run_retention_days", self.run_retention_days.value())
        self.settings.set("logging.command_debug_enabled", self.command_debug_enabled.isChecked())
