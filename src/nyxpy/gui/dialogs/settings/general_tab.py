from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class GeneralSettingsTab(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("一般設定項目（今後拡張予定）"))

    def apply(self):
        # 今後、一般設定の保存処理をここに実装
        pass
