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
from nyxpy.framework.core.hardware.facade import HardwareFacade
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Settings service aggregates global settings, capture and serial managers
        self.settings_service = SettingsService()
        # Alias for backward compatibility
        self.global_settings = self.settings_service.global_settings
        self.capture_manager = self.settings_service.capture_manager
        self.serial_manager = self.settings_service.serial_manager
        # Initialize macro executor for browser pane
        self.executor = MacroExecutor()

        # Set up the basic UI first to show it quickly
        self.setup_ui()

        # Use Qt's event queue to initialize the rest after UI appears
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self.deferred_init)

    def deferred_init(self):
        """Perform initialization that can be deferred until after UI appears"""
        self.init_managers()
        self.setup_logging()  # Setup logging for the GUI
        self.setup_connections()  # Setup signal connections between UI components

    def init_managers(self):
        # Load settings and initialize hardware managers
        # シリアルデバイスの初期化 (already started in background by SettingsService)
        # Just log status
        if not self.serial_manager.is_active():
            log_manager.log(
                "WARNING",
                "シリアルデバイスが見つからないか、初期化に失敗しました。設定ダイアログから再設定してください。",
                "MainWindow",
            )

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
        self.virtual_controller = VirtualControllerPane(self, self.serial_manager)

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
            settings_service=self.settings_service, parent=self
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
        self.control_pane.run_requested.connect(self.start_macro)
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
            capture_manager=self.capture_manager,
            serial_manager=self.serial_manager,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        # 設定が保存された場合に各マネージャを更新
        new_cap = self.global_settings.get("capture_device")
        try:
            self.preview_pane.set_active_device(new_cap)
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
            self.serial_manager.set_active(new_ser, new_baud)
            # シリアルマネージャーを仮想コントローラにも設定して同期させる
            self.virtual_controller.model.set_serial_manager(self.serial_manager)
            log_manager.log(
                "INFO",
                f"シリアルデバイスを設定しました: {new_ser} ({new_baud}bps)",
                "MainWindow",
            )
        except Exception as e:
            log_manager.log("ERROR", f"シリアルデバイス設定エラー: {e}", "MainWindow")

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

    def start_macro(self):
        macro_name = self.macro_browser.table.item(
            self.macro_browser.table.currentRow(), 0
        ).text()
        dlg = SettingsDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        params = dlg.param_edit.text()
        exec_args = parse_define_args(params)
        resource_io = StaticResourceIO(Path.cwd() / "static")
        # 設定サービスから選択されたプロトコルを取得
        protocol = self.settings_service.get_protocol()
        ct = CancellationToken()
        facade = HardwareFacade(self.serial_manager, self.capture_manager)
        cmd = DefaultCommand(facade, resource_io, protocol, ct)

        self.worker = WorkerThread(self.executor, cmd, macro_name, exec_args)
        self.worker.finished.connect(self.on_finished)

        self.control_pane.run_btn.setEnabled(False)
        self.control_pane.settings_btn.setEnabled(False)
        self.control_pane.cancel_btn.setEnabled(True)
        self.status_label.setText("実行中")
        self.worker.start()

    def cancel_macro(self):
        if hasattr(self, "worker"):
            self.worker.cmd.stop()
            self.control_pane.cancel_btn.setEnabled(False)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.control_pane.run_btn.setEnabled(True)
        self.control_pane.settings_btn.setEnabled(True)
        self.control_pane.cancel_btn.setEnabled(False)
        if status.startswith("エラー"):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("エラー")
            dlg.setText(f"マクロ実行中にエラーが発生しました:\n{status}")
            dlg.setStandardButtons(QMessageBox.Retry | QMessageBox.Close)
            ret = dlg.exec()
            if ret == QMessageBox.Retry:
                self.start_macro()
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
