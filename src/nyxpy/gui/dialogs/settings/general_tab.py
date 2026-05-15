from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

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
        layout.addLayout(form)

    def apply(self):
        self.settings.set("gui.window_size_preset", self.window_size_preset.currentData())
