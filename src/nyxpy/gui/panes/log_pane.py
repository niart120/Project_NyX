from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QSizePolicy, QHBoxLayout, QPushButton, QCheckBox
from nyxpy.framework.core.logger.log_manager import log_manager


class LogPane(QWidget):
    """
    Pane for displaying real-time logs in a read-only text view.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        # 操作パネル（自動スクロールON/OFF, デバッグログ表示切替, Clearボタン）
        control_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("自動スクロール", self)
        self.auto_scroll_checkbox.setChecked(True)
        self.debug_checkbox = QCheckBox("デバッグログ表示", self)
        self.debug_checkbox.setChecked(False)
        self.clear_button = QPushButton("Clear", self)
        control_layout.addWidget(self.auto_scroll_checkbox)
        control_layout.addWidget(self.debug_checkbox)
        control_layout.addWidget(self.clear_button)
        control_layout.addStretch(1)
        main_layout.addLayout(control_layout)
        # ログ表示部
        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setMinimumWidth(0)
        # Also allow pane itself to shrink
        self.setMinimumWidth(0)
        main_layout.addWidget(self.view)
        # Clearボタンのシグナル接続
        self.clear_button.clicked.connect(self.view.clear)
        # LogManagerにGUI用ハンドラを追加
        log_manager.add_handler(self.append, level="DEBUG")
        self.debug_checkbox.stateChanged.connect(self._on_debug_checkbox_changed)

    def append(self, message: str):
        """Append a new log message to the view."""
        self.view.appendPlainText(message)
        if self.auto_scroll_checkbox.isChecked():
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def closeEvent(self, event):
        # LogManagerからハンドラを削除（多重登録・多重出力防止）
        log_manager.remove_handler(self.append)
        super().closeEvent(event)

    def _on_debug_checkbox_changed(self, state):
        # チェックON: DEBUG, OFF: INFO
        level = "DEBUG" if self.debug_checkbox.isChecked() else "INFO"
        try:
            log_manager.set_custom_handler_level(self.append, level)
        except Exception:
            pass  # 初回登録前などは無視
