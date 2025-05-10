from PySide6.QtCore import QThread, Signal, QTimer
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
from nyxpy.framework.core.macro.command import Command, DefaultCommand
from nyxpy.framework.core.utils.cancellation import CancellationToken
from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog
from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.control_pane import ControlPane
from pathlib import Path
from copy import deepcopy
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane
from nyxpy.framework.core.singletons import global_settings, serial_manager, capture_manager, secrets_settings, initialize_managers
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.api.notification_handler import create_notification_handler_from_settings
from nyxpy.gui.events import EventBus, EventType


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        initialize_managers()
        self.executor = MacroExecutor()
        self._last_settings = {}
        self.setup_ui()
        QTimer.singleShot(100, self.deferred_init)

    def deferred_init(self):
        """Perform initialization that can be deferred until after UI appears"""
        self.setup_connections()  # Setup signal connections between UI components
        self.apply_app_settings()

    def setup_ui(self):
        self.setWindowTitle("NyxPy GUI")
        self.resize(1000, 600)
        self.setMinimumSize(800, 400)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_app_settings)
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
        self.virtual_controller = VirtualControllerPane(self)

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
            capture_device=capture_manager.get_active_device(),
            parent=self,
            preview_fps=global_settings.get("preview_fps", 30)
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
        self.control_pane.settings_requested.connect(self.open_app_settings)

        # Set status to ready
        self.status_label.setText("準備完了")

    def open_app_settings(self):
        dlg = AppSettingsDialog(self, global_settings, secrets_settings)
        dlg.settings_applied.connect(self.apply_app_settings)
        if dlg.exec() != QDialog.Accepted:
            return
        self.apply_app_settings()

    def apply_app_settings(self):
        prev = self._last_settings
        cur = global_settings.data
        diff_keys = {k for k in cur if prev.get(k) != cur.get(k)}
        # 差分がある項目のみ反映・イベント発行
        if "serial_device" in diff_keys or "serial_baud" in diff_keys:
            try:
                serial_manager.set_active(cur.get("serial_device"), cur.get("serial_baud", 9600))
                EventBus.get_instance().publish(EventType.SERIAL_DEVICE_CHANGED, {
                    'name': cur.get("serial_device"),
                    'baudrate': cur.get("serial_baud", 9600),
                    'device': serial_manager.get_active_device()
                })
                log_manager.log(
                    "INFO",
                    f"シリアルデバイスを切り替えました: {cur.get('serial_device')} ({cur.get('serial_baud', 9600)} bps)",
                    "MainWindow",
                )
            except Exception as e:
                log_manager.log(
                    "ERROR", f"シリアルデバイス切り替えエラー: {e}", "MainWindow"
                )
        if "capture_device" in diff_keys:
            try:
                capture_manager.set_active(cur.get("capture_device"))
                EventBus.get_instance().publish(EventType.CAPTURE_DEVICE_CHANGED, {
                    'name': cur.get("capture_device"),
                    'device': capture_manager.get_active_device()
                })
                log_manager.log(
                    "INFO", f"キャプチャデバイスを切り替えました: {cur.get('capture_device')}", "MainWindow"
                )
            except Exception as e:
                log_manager.log(
                    "ERROR", f"キャプチャデバイス切り替えエラー: {e}", "MainWindow"
                )
        if "serial_protocol" in diff_keys:
            try:
                protocol = ProtocolFactory.create_protocol(cur.get("serial_protocol", "CH552"))
                EventBus.get_instance().publish(EventType.PROTOCOL_CHANGED, {"protocol": protocol})
                protocol_name = cur.get("serial_protocol", "CH552")
                log_manager.log(
                    "INFO",
                    f"コントローラープロトコルを切り替えました: {protocol_name}",
                    "MainWindow",
                )
            except Exception as e:
                log_manager.log("ERROR", f"プロトコル切り替えエラー: {e}", "MainWindow")
        if "preview_fps" in diff_keys:
            self.preview_pane.preview_fps = cur.get("preview_fps", 30)
            self.preview_pane.apply_fps()
        
        # 通知設定の変更処理
        notification_settings_changed = False
        
        # シークレット設定から通知関連の設定変更を確認
        if secrets_settings.get("notification.discord.enabled") != prev.get("notification.discord.enabled") or \
           secrets_settings.get("notification.bluesky.enabled") != prev.get("notification.bluesky.enabled"):
            notification_settings_changed = True
        
        # 通知設定が変更された場合はログに出力
        if notification_settings_changed:
            enabled_services = []
            if secrets_settings.get("notification.discord.enabled", False):
                enabled_services.append("Discord")
            if secrets_settings.get("notification.bluesky.enabled", False):
                enabled_services.append("Bluesky")
            
            if enabled_services:
                log_manager.log(
                    "INFO",
                    f"通知設定が変更されました。有効なサービス: {', '.join(enabled_services)}",
                    "MainWindow"
                )
            else:
                log_manager.log(
                    "INFO",
                    "通知設定が変更されました。全てのサービスが無効です。",
                    "MainWindow"
                )
                
        # ...他の設定も必要に応じて追加...
        self._last_settings = deepcopy(cur)

    def execute_macro_immediate(self):
        """即時実行モード：パラメータ入力なしでマクロを実行する"""
        self._start_macro({})  # 空のパラメータ辞書を渡す

    def execute_macro_with_params(self):
        """パラメータ付き実行モード：パラメータ入力ダイアログを表示して実行する"""
        macro_name = self.macro_browser.table.item(
            self.macro_browser.table.currentRow(), 0
        ).text()
        dlg = MacroParamsDialog(self, macro_name)
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
        protocol = ProtocolFactory.create_protocol(global_settings.get("serial_protocol", "CH552"))
        ct = CancellationToken()
        notification_handler = create_notification_handler_from_settings(secrets_settings)
        cmd = DefaultCommand(
            serial_device=serial_manager.get_active_device(),
            capture_device=capture_manager.get_active_device(),
            resource_io=resource_io,
            protocol=protocol,
            ct=ct,
            notification_handler=notification_handler,
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
            self.control_pane.set_running(False)  # 状態管理に統一

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
        self.executor: MacroExecutor = executor
        self.cmd: Command = cmd

        self.macro_name = macro_name
        self.args = args

    def run(self):
        try:
            self.executor.set_active_macro(self.macro_name)
            self.executor.execute(self.cmd, self.args)
            self.finished.emit("完了")
        except MacroStopException:
            self.finished.emit("中断")
        except Exception as e:
            self.finished.emit(f"エラー: {e}")
