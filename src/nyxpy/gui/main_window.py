from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.api.notification_handler import create_notification_handler_from_settings
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.logger import create_default_logging
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import create_legacy_runtime_builder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.singletons import (
    capture_manager,
    global_settings,
    initialize_managers,
    secrets_settings,
    serial_manager,
)
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog
from nyxpy.gui.events import EventBus, EventType
from nyxpy.gui.panes.control_pane import ControlPane
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logging = create_default_logging(base_dir=Path.cwd() / "logs", console_enabled=False)
        self.logger = self.logging.logger
        capture_manager.set_logger(self.logger)
        initialize_managers()
        self.registry = MacroRegistry(project_root=Path.cwd())
        self.macro_catalog = MacroCatalog(self.registry)
        self._last_settings = {}
        self._last_secrets = {}
        self.run_handle: RunHandle | None = None
        self.last_run_result: RunResult | None = None
        self._run_poll_timer = QTimer(self)
        self._run_poll_timer.timeout.connect(self._poll_run_handle)
        self.setup_ui()
        QTimer.singleShot(100, self.deferred_init)

    def deferred_init(self):
        """Perform initialization that can be deferred until after UI appears"""
        self.setup_connections()  # Setup signal connections between UI components
        self.apply_app_settings()

    def setup_ui(self):
        self.setWindowTitle("NyxPy GUI")
        self.resize(1280, 720)
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
        self.macro_browser = MacroBrowserPane(self.macro_catalog, self)
        # Give macro_browser vertical stretch so it fills the pane
        left_layout.addWidget(self.macro_browser, 1)

        # 仮想コントローラーペインを作成
        self.virtual_controller = VirtualControllerPane(self.logger, self)

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
            preview_fps=global_settings.get("preview_fps", 30),
        )
        right_layout.addWidget(self.preview_pane, stretch=1)

        # Log pane
        self.log_pane = LogPane(self.logging.dispatcher, self)
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
        self.control_pane.run_with_params_requested.connect(self.execute_macro_with_params)
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
        prev_global, prev_secrets = self._last_settings, self._last_secrets
        cur_global = global_settings.data
        cur_secrets = secrets_settings.data

        # 設定差分を取得
        diff_keys = set()
        # グローバル
        diff_keys.update({k for k in cur_global if prev_global.get(k) != cur_global.get(k)})
        # シークレット
        diff_keys.update({k for k in cur_secrets if prev_secrets.get(k) != cur_secrets.get(k)})

        # 差分がある項目のみ反映・イベント発行
        if "serial_device" in diff_keys or "serial_baud" in diff_keys:
            try:
                serial_manager.set_active(
                    cur_global.get("serial_device"), cur_global.get("serial_baud", 9600)
                )
                EventBus.get_instance().publish(
                    EventType.SERIAL_DEVICE_CHANGED,
                    {
                        "name": cur_global.get("serial_device"),
                        "baudrate": cur_global.get("serial_baud", 9600),
                        "device": serial_manager.get_active_device(),
                    },
                )
                self.logger.user(
                    "INFO",
                    f"シリアルデバイスを切り替えました: {cur_global.get('serial_device')} ({cur_global.get('serial_baud', 9600)} bps)",
                    component="MainWindow",
                    event="configuration.changed",
                )
            except Exception as e:
                self.logger.technical(
                    "ERROR",
                    "シリアルデバイス切り替えエラー",
                    component="MainWindow",
                    event="configuration.invalid",
                    exc=e,
                )
        if "capture_device" in diff_keys:
            try:
                capture_manager.set_active(cur_global.get("capture_device"))
                EventBus.get_instance().publish(
                    EventType.CAPTURE_DEVICE_CHANGED,
                    {
                        "name": cur_global.get("capture_device"),
                        "device": capture_manager.get_active_device(),
                    },
                )
                self.logger.user(
                    "INFO",
                    f"キャプチャデバイスを切り替えました: {cur_global.get('capture_device')}",
                    component="MainWindow",
                    event="configuration.changed",
                )
            except Exception as e:
                self.logger.technical(
                    "ERROR",
                    "キャプチャデバイス切り替えエラー",
                    component="MainWindow",
                    event="configuration.invalid",
                    exc=e,
                )
        if "serial_protocol" in diff_keys:
            try:
                protocol = ProtocolFactory.create_protocol(
                    cur_global.get("serial_protocol", "CH552")
                )
                EventBus.get_instance().publish(EventType.PROTOCOL_CHANGED, {"protocol": protocol})
                protocol_name = cur_global.get("serial_protocol", "CH552")
                self.logger.user(
                    "INFO",
                    f"コントローラープロトコルを切り替えました: {protocol_name}",
                    component="MainWindow",
                    event="configuration.changed",
                )
            except Exception as e:
                self.logger.technical(
                    "ERROR",
                    "プロトコル切り替えエラー",
                    component="MainWindow",
                    event="configuration.invalid",
                    exc=e,
                )
        if "preview_fps" in diff_keys:
            self.preview_pane.preview_fps = cur_global.get("preview_fps", 30)
            self.preview_pane.apply_fps()

        # シークレット設定から通知関連の設定変更を確認
        if (
            "notification.discord.enabled" in diff_keys
            or "notification.bluesky.enabled" in diff_keys
        ):
            enabled_services = []
            if secrets_settings.get("notification.discord.enabled", False):
                enabled_services.append("Discord")
            if secrets_settings.get("notification.bluesky.enabled", False):
                enabled_services.append("Bluesky")

            if enabled_services:
                self.logger.user(
                    "INFO",
                    f"通知設定が変更されました。有効なサービス: {', '.join(enabled_services)}",
                    component="MainWindow",
                    event="configuration.changed",
                )
            else:
                self.logger.user(
                    "INFO",
                    "通知設定が変更されました。全てのサービスが無効です。",
                    component="MainWindow",
                    event="configuration.changed",
                )

        # ...他の設定も必要に応じて追加...
        self._last_settings = deepcopy(cur_global)
        self._last_secrets = deepcopy(cur_secrets)

    def execute_macro_immediate(self):
        """即時実行モード：パラメータ入力なしでマクロを実行する"""
        self._start_macro({})  # 空のパラメータ辞書を渡す

    def execute_macro_with_params(self):
        """パラメータ付き実行モード：パラメータ入力ダイアログを表示して実行する"""
        macro_name = self.macro_browser.table.item(self.macro_browser.table.currentRow(), 0).text()
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
        macro_name = self.macro_browser.table.item(self.macro_browser.table.currentRow(), 0).text()
        builder = self._create_runtime_builder()
        self.run_handle = builder.start(
            RuntimeBuildRequest(macro_id=macro_name, entrypoint="gui", exec_args=exec_args)
        )
        self.control_pane.set_running(True)
        self.status_label.setText("実行中")
        self._run_poll_timer.start(global_settings.get("runtime.gui_poll_interval_ms", 100))

    def _create_runtime_builder(self):
        protocol = ProtocolFactory.create_protocol(global_settings.get("serial_protocol", "CH552"))
        notification_handler = create_notification_handler_from_settings(
            secrets_settings,
            logger=self.logger,
        )
        return create_legacy_runtime_builder(
            project_root=Path.cwd(),
            registry=self.registry,
            serial_device=serial_manager.get_active_device(),
            capture_device=capture_manager.get_active_device(),
            protocol=protocol,
            notification_handler=notification_handler,
            logger=self.logger,
        )

    def cancel_macro(self):
        if self.run_handle is not None and not self.run_handle.done():
            self.run_handle.cancel()
            self.status_label.setText("中断要求中")
        self.control_pane.set_running(False)  # 状態管理に統一

    def _poll_run_handle(self) -> None:
        if self.run_handle is None or not self.run_handle.done():
            return
        self._run_poll_timer.stop()
        try:
            self.last_run_result = self.run_handle.result()
            status = self._format_run_result(self.last_run_result)
        except Exception as exc:
            status = f"エラー: {exc}"
        self.run_handle = None
        self.on_finished(status)

    def _format_run_result(self, result: RunResult) -> str:
        if result.status is RunStatus.SUCCESS:
            return "完了"
        if result.status is RunStatus.CANCELLED:
            return "中断"
        message = result.error.message if result.error is not None else "不明なエラー"
        return f"エラー: {message}"

    def closeEvent(self, event):
        """ウィンドウ終了時にリソースを確実に解放する。"""
        self.logger.user(
            "INFO",
            "アプリケーションを終了します...",
            component="MainWindow",
            event="application.closing",
        )

        # 1. マクロ実行中なら停止を要求し、完了を待つ
        if self.run_handle is not None and not self.run_handle.done():
            self.run_handle.cancel()
            if not self.run_handle.wait(5):
                self.logger.technical(
                    "WARNING",
                    "Runtime handle の終了がタイムアウトしました",
                    component="MainWindow",
                    event="macro.cancelled",
                )

        # 2. プレビュータイマーを停止
        self.preview_pane.timer.stop()

        # 3. キャプチャデバイスを解放（バックグラウンドスレッド停止）
        try:
            capture_manager.release_active()
        except Exception as e:
            self.logger.technical(
                "WARNING",
                "キャプチャデバイス解放エラー",
                component="MainWindow",
                event="capture.release_failed",
                exc=e,
            )

        # 4. シリアルデバイスを解放
        try:
            serial_manager.close_active()
        except Exception as e:
            self.logger.technical(
                "WARNING",
                "シリアルデバイス解放エラー",
                component="MainWindow",
                event="serial.close_failed",
                exc=e,
            )

        self.logging.close()
        super().closeEvent(event)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.control_pane.set_running(False)

        if status.startswith("エラー"):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("エラー")
            dlg.setText(f"マクロ実行中にエラーが発生しました:\n{status}")
            dlg.setStandardButtons(QMessageBox.Retry | QMessageBox.Close)
            ret = dlg.exec()
            # リトライまたは閉じるの選択肢を処理
            if ret == QMessageBox.Retry:
                # リトライ時は現在のマクロを再実行
                self._start_macro({})

            elif ret == QMessageBox.Close:
                # 閉じる場合は何もしない
                pass


class MacroCatalog:
    def __init__(self, registry: MacroRegistry) -> None:
        self.registry = registry
        self.macros = {}
        self.reload_macros()

    def reload_macros(self) -> None:
        self.registry.reload()
        self.macros = {
            definition.class_name: definition
            for definition in self.registry.list(include_failed=False)
        }
