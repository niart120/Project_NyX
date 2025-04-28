from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QLabel,
    QDialog,
)

from nyxpy.framework.core.hardware.resource import StaticResourceIO
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.utils.cancellation import CancellationToken
from nyxpy.gui.dialogs.settings_dialog import SettingsDialog
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.gui.dialogs.device_settings_dialog import DeviceSettingsDialog
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.control_pane import ControlPane
from pathlib import Path
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.framework.core.settings_service import SettingsService
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane
from nyxpy.gui.models.device_model import DeviceModel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.global_settings = self.settings_service.global_settings
        self.device_model = DeviceModel()
        self.executor = MacroExecutor()
        self.setup_ui()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.deferred_init)

    def deferred_init(self):
        """Perform initialization that can be deferred until after UI appears"""
        self.setup_logging()  # Setup logging for the GUI
        self.setup_connections()  # Setup signal connections between UI components

    def setup_ui(self):
        self.setWindowTitle("NyxPy GUI")
        self.resize(1000, 600)
        self.setMinimumSize(800, 400)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(settings_action)

        central = QWidget()
        main_layout = QHBoxLayout(central)
        self.setCentralWidget(central)

        # Left container: macro browser, controls, and virtual controller
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        self.macro_browser = MacroBrowserPane(self.executor, self)
        # Give macro_browser vertical stretch so it fills the pane
        left_layout.addWidget(self.macro_browser, 1)

        # 仮想コントローラーペインを作成
        self.virtual_controller = VirtualControllerPane(self, self.device_model)

        # Control pane and Virtual Controller in lower section
        lower_section = QVBoxLayout()

        # Control pane at bottom with default stretch
        self.control_pane = ControlPane(self)
        lower_section.addWidget(self.control_pane)

        # 仮想コントローラーを下部に追加
        lower_section.addWidget(self.virtual_controller)

        left_layout.addLayout(lower_section)
        main_layout.addWidget(left_container)

        # Right pane: preview and log
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        # Preview pane replaces direct label
        self.preview_pane = PreviewPane(
            settings_service=self.settings_service,
            capture_device=self.device_model.active_capture_device,
            parent=self
        )
        right_layout.addWidget(self.preview_pane, stretch=1)

        # Log pane
        self.log_pane = LogPane(self)
        right_layout.addWidget(self.log_pane, stretch=1)

        # Set stretch for log pane to fill remaining space
        main_layout.addWidget(right_container, stretch=1)

        # status bar
        self.status_label = QLabel("準備中...")
        self.statusBar().addWidget(self.status_label)

    def setup_connections(self):
        # Connect pane signals fully delegated
        self.macro_browser.selection_changed.connect(self.control_pane.set_selection)
        self.control_pane.run_requested.connect(self.execute_macro_immediate)
        self.control_pane.run_with_params_requested.connect(
            self.execute_macro_with_params
        )
        self.control_pane.cancel_requested.connect(self.cancel_macro)
        # Delegate snapshot to PreviewPane and status via signal
        self.control_pane.snapshot_requested.connect(self.preview_pane.take_snapshot)
        self.preview_pane.snapshot_taken.connect(self.status_label.setText)
        self.control_pane.settings_requested.connect(self.open_settings)

        # Set status to ready
        self.status_label.setText("準備完了")

    def setup_logging(self):
        log_manager.add_handler(
            lambda record: self.log_pane.append(str(record)), level="DEBUG"
        )

    def open_settings(self):
        # 更新したDialogに既存のマネージャを渡す
        dlg = DeviceSettingsDialog(
            self,
            self.global_settings,
            capture_manager=None,  # DeviceModel経由に統一するため不要
            serial_manager=None,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        # 設定が保存された場合に各マネージャを更新
        new_cap = self.global_settings.get("capture_device")
        try:
            self.device_model.change_capture_device(new_cap)
            self.preview_pane.set_capture_device(self.device_model.active_capture_device)
            log_manager.log(
                "INFO", f"キャプチャデバイスを切り替えました: {new_cap}", "MainWindow"
            )
        except Exception as e:
            log_manager.log(
                "ERROR", f"キャプチャデバイス切り替えエラー: {e}", "MainWindow"
            )

        new_ser = self.global_settings.get("serial_device")
        new_baud = self.global_settings.get("serial_baud", 9600)
        try:
            self.device_model.change_serial_device(new_ser, new_baud)
            self.virtual_controller.model.set_serial_device(self.device_model.active_serial_device)
            log_manager.log(
                "INFO",
                f"シリアルデバイスを切り替えました: {new_ser} ({new_baud} bps)",
                "MainWindow",
            )
        except Exception as e:
            log_manager.log(
                "ERROR", f"シリアルデバイス切り替えエラー: {e}", "MainWindow"
            )

        # プロトコル設定が変更されている場合は、仮想コントローラのプロトコルも更新
        try:
            # SettingsServiceから現在のプロトコルを取得
            protocol = self.settings_service.get_protocol()
            # 仮想コントローラにプロトコルを設定
            self.virtual_controller.model.set_protocol(protocol)
            protocol_name = self.global_settings.get("serial_protocol", "CH552")
            log_manager.log(
                "INFO",
                f"コントローラープロトコルを切り替えました: {protocol_name}",
                "MainWindow",
            )
        except Exception as e:
            log_manager.log("ERROR", f"プロトコル切り替えエラー: {e}", "MainWindow")

        self.preview_pane.apply_fps()

    def execute_macro_immediate(self):
        """即時実行モード：パラメータ入力なしでマクロを実行する"""
        self._start_macro({})  # 空のパラメータ辞書を渡す

    def execute_macro_with_params(self):
        """パラメータ付き実行モード：パラメータ入力ダイアログを表示して実行する"""
        macro_name = self.macro_browser.table.item(
            self.macro_browser.table.currentRow(), 0
        ).text()
        dlg = SettingsDialog(self, macro_name)
        if dlg.exec() != QDialog.Accepted:
            return

        # パラメータを解析して実行に渡す
        params = dlg.param_edit.text()
        exec_args = parse_define_args(params)
        self._start_macro(exec_args)

    def _start_macro(self, exec_args):
        """
        共通のマクロ実行処理

        Args:
            exec_args: マクロに渡す引数辞書
        """
        macro_name = self.macro_browser.table.item(
            self.macro_browser.table.currentRow(), 0
        ).text()
        resource_io = StaticResourceIO(Path.cwd() / "static")
        protocol = self.settings_service.get_protocol()
        ct = CancellationToken()
        # HardwareFacadeは不要、DeviceModel経由でデバイスを直接渡す
        cmd = DefaultCommand(
            serial_device=self.device_model.active_serial_device,
            capture_device=self.device_model.active_capture_device,
            resource_io=resource_io,
            protocol=protocol,
            ct=ct,
        )
        self.worker = WorkerThread(self.executor, cmd, macro_name, exec_args)
        self.worker.progress.connect(self.log_pane.append)
        self.worker.finished.connect(self.on_finished)
        self.control_pane.set_running(True)
        self.status_label.setText("実行中")
        self.worker.start()

    def cancel_macro(self):
        if hasattr(self, "worker"):
            self.worker.cmd.stop()
            self.control_pane.cancel_btn.setEnabled(False)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.control_pane.set_running(False)

        if status.startswith("エラー"):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("エラー")
            dlg.setText(f"マクロ実行中にエラーが発生しました:\n{status}")
            dlg.setStandardButtons(QMessageBox.Retry | QMessageBox.Close)
            ret = dlg.exec()
            if ret == QMessageBox.Retry:
                self._start_macro({})
            elif ret == QMessageBox.Close:
                from PySide6.QtWidgets import QApplication

                QApplication.instance().quit()


class WorkerThread(QThread):
    progress = Signal(str)
    finished = Signal(str)

    def __init__(self, executor, cmd, macro_name, args):
        super().__init__()
        self.executor = executor
        self.cmd = cmd
        orig_log = getattr(self.cmd, "log", None)

        def _log_override(*values, sep=" ", end="\n", level="INFO"):
            msg = sep.join(map(str, values)) + end.rstrip("\n")
            self.progress.emit(msg)
            if orig_log:
                orig_log(*values, sep=sep, end=end, level=level)

        self.cmd.log = _log_override
        self.macro_name = macro_name
        self.args = args

    def run(self):
        try:
            self.executor.select_macro(self.macro_name)
            self.executor.execute(self.cmd, self.args)
            self.finished.emit("完了")
        except MacroStopException:
            self.finished.emit("中断")
        except Exception as e:
            self.finished.emit(f"エラー: {e}")
