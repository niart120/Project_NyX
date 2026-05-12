from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from nyxpy.gui.widgets.split_button import CustomSplitDropDownButton


class RunUiState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FINISHED = "finished"


class ControlPane(QWidget):
    """
    Pane for macro control buttons: run, cancel, settings, snapshot.
    """

    run_requested = Signal()
    run_with_params_requested = Signal()
    cancel_requested = Signal()
    settings_requested = Signal()
    snapshot_requested = Signal()
    running_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        # Buttons

        # Create run button as a split button with dropdown for "with parameters" option
        self.run_btn = CustomSplitDropDownButton(
            "実行", [("パラメータ付きで実行", self._on_run_with_params)], self
        )

        self.cancel_btn = QPushButton("キャンセル", self)
        self.snapshot_btn = QPushButton("スナップショット", self)
        self.settings_btn = QPushButton("設定", self)

        layout.addWidget(self.run_btn)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.snapshot_btn)
        layout.addStretch()
        layout.addWidget(self.settings_btn)

        # Connect signals
        self.run_btn.main_clicked.connect(self.run_requested)
        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.settings_btn.clicked.connect(self.settings_requested)
        self.snapshot_btn.clicked.connect(self.snapshot_requested)

        self._selected = False
        self._run_state = RunUiState.IDLE
        self.update_buttons()

    def _on_run_with_params(self):
        """Handler for the 'Run with parameters' dropdown option"""
        self.run_with_params_requested.emit()

    def set_selection(self, selected: bool):
        self._selected = selected
        self.update_buttons()

    def set_run_state(self, state: RunUiState):
        self._run_state = state
        self.running_changed.emit(state is RunUiState.RUNNING)
        self.update_buttons()

    def update_buttons(self):
        running = self._run_state in {RunUiState.RUNNING, RunUiState.CANCELLING}
        self.run_btn.setEnabled(self._selected and not running)
        self.settings_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(self._run_state is RunUiState.RUNNING)
        self.snapshot_btn.setEnabled(not running)
