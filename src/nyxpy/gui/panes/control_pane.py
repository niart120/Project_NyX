from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal

class ControlPane(QWidget):
    """
    Pane for macro control buttons: run, cancel, settings, snapshot.
    """
    run_requested = Signal()
    cancel_requested = Signal()
    settings_requested = Signal()
    snapshot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        # Buttons
        self.run_btn = QPushButton("実行", self)
        self.cancel_btn = QPushButton("キャンセル", self)
        self.snapshot_btn = QPushButton("スナップショット", self)
        self.settings_btn = QPushButton("設定", self)
        # Initial states
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        layout.addWidget(self.run_btn)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.snapshot_btn)
        layout.addStretch()
        layout.addWidget(self.settings_btn)

        # Connect signals
        self.run_btn.clicked.connect(self.run_requested)
        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.settings_btn.clicked.connect(self.settings_requested)
        self.snapshot_btn.clicked.connect(self.snapshot_requested)

    def set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.settings_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def set_selection(self, selected: bool):
        self.run_btn.setEnabled(selected)