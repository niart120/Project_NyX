from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QSizePolicy, QWidget

from nyxpy.gui.widgets.split_button import CustomSplitDropDownButton

_CONTROL_BUTTON_HEIGHT = 34


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

    def __init__(self, parent=None, *, horizontal_margin: int = 0):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(horizontal_margin, 0, horizontal_margin, 0)
        self._layout.setSpacing(6)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)
        # Buttons

        # Create run button as a split button with dropdown for "with parameters" option
        self.run_btn = CustomSplitDropDownButton(
            "実行", [("パラメータ付きで実行", self._on_run_with_params)], self
        )

        self.cancel_btn = QPushButton("停止", self)
        self.snapshot_btn = QPushButton("スナップショット", self)
        self.settings_btn = QPushButton("設定", self)

        self._configure_button_sizes()
        self._arrange_buttons()

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

    def _arrange_buttons(self) -> None:
        for widget in (self.run_btn, self.cancel_btn, self.snapshot_btn, self.settings_btn):
            self._layout.removeWidget(widget)
        self._layout.addWidget(self.run_btn, 0, 0)
        self._layout.addWidget(self.cancel_btn, 0, 1)
        self._layout.addWidget(self.snapshot_btn, 1, 0)
        self._layout.addWidget(self.settings_btn, 1, 1)

    def _configure_button_sizes(self) -> None:
        for button in (self.run_btn, self.cancel_btn, self.snapshot_btn, self.settings_btn):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setFixedHeight(_CONTROL_BUTTON_HEIGHT)
        self.run_btn.mainButton.setFixedHeight(_CONTROL_BUTTON_HEIGHT)
        self.run_btn.dropdownButton.setFixedHeight(_CONTROL_BUTTON_HEIGHT)

    def update_buttons(self):
        running = self._run_state in {RunUiState.RUNNING, RunUiState.CANCELLING}
        self.run_btn.setEnabled(self._selected and not running)
        self.settings_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(self._run_state is RunUiState.RUNNING)
        self.snapshot_btn.setEnabled(not running)
        if self._run_state is RunUiState.CANCELLING:
            self.cancel_btn.setText("中断要求中")
        else:
            self.cancel_btn.setText("停止")
