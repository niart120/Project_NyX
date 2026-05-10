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
from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.io.device_factories import (
    ControllerOutputPortFactory,
    FrameSourcePortFactory,
)
from nyxpy.framework.core.logger import create_default_logging
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import (
    MacroRuntimeBuilder,
    create_device_runtime_builder,
)
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog
from nyxpy.gui.events import EventBus, EventType
from nyxpy.gui.macro_catalog import MacroCatalog
from nyxpy.gui.panes.control_pane import ControlPane
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_root = Path.cwd()
        self.logging = create_default_logging(
            base_dir=self.project_root / "logs",
            console_enabled=False,
        )
        self.logger = self.logging.logger
        self.global_settings = GlobalSettings()
        self.secrets_settings = SecretsSettings()
        self.device_discovery = DeviceDiscoveryService(logger=self.logger)
        self.runtime_builder: MacroRuntimeBuilder | None = None
        self.registry = MacroRegistry(project_root=self.project_root)
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
            parent=self,
            preview_fps=self.global_settings.get("preview_fps", 30),
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
        dlg = AppSettingsDialog(
            self,
            self.global_settings,
            self.secrets_settings,
            device_discovery=self.device_discovery,
        )
        dlg.settings_applied.connect(self.apply_app_settings)
        if dlg.exec() != QDialog.Accepted:
            return
        self.apply_app_settings()

    def apply_app_settings(self):
        prev_global, prev_secrets = self._last_settings, self._last_secrets
        cur_global = self.global_settings.data
        cur_secrets = self.secrets_settings.data

        # 設定差分を取得
        diff_keys = set()
        # グローバル
        diff_keys.update({k for k in cur_global if prev_global.get(k) != cur_global.get(k)})
        # シークレット
        diff_keys.update({k for k in cur_secrets if prev_secrets.get(k) != cur_secrets.get(k)})

        # 差分がある項目のみ反映・イベント発行
        if "serial_device" in diff_keys or "serial_baud" in diff_keys:
            self.logger.user(
                "INFO",
                f"シリアルデバイス設定を更新しました: {cur_global.get('serial_device')} ({cur_global.get('serial_baud', 9600)} bps)",
                component="MainWindow",
                event="configuration.changed",
            )
        if "capture_device" in diff_keys:
            self.logger.user(
                "INFO",
                f"キャプチャデバイス設定を更新しました: {cur_global.get('capture_device')}",
                component="MainWindow",
                event="configuration.changed",
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
            self.preview_pane.preview_fps = self.global_settings.get("preview_fps", 30)
            self.preview_pane.apply_fps()

        # シークレット設定から通知関連の設定変更を確認
        if (
            "notification.discord.enabled" in diff_keys
            or "notification.bluesky.enabled" in diff_keys
        ):
            enabled_services = []
            if self.secrets_settings.get("notification.discord.enabled", False):
                enabled_services.append("Discord")
            if self.secrets_settings.get("notification.bluesky.enabled", False):
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
        if diff_keys or self.runtime_builder is None:
            self._replace_runtime_builder()

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
        self._run_poll_timer.start(self.global_settings.get("runtime.gui_poll_interval_ms", 100))

    def _create_runtime_builder(self):
        if self.runtime_builder is None:
            self._replace_runtime_builder()
        assert self.runtime_builder is not None
        return self.runtime_builder

    def _replace_runtime_builder(self) -> None:
        previous_builder = self.runtime_builder
        protocol = ProtocolFactory.create_protocol(
            self.global_settings.get("serial_protocol", "CH552")
        )
        discovery = self.device_discovery
        controller_factory = ControllerOutputPortFactory(
            discovery=discovery,
            protocol=protocol,
        )
        frame_factory = FrameSourcePortFactory(
            discovery=discovery,
            logger=self.logger,
        )
        notification_handler = create_notification_handler_from_settings(
            self.secrets_settings.snapshot(),
            logger=self.logger,
        )
        self.runtime_builder = create_device_runtime_builder(
            project_root=self.project_root,
            registry=self.registry,
            device_discovery=discovery,
            controller_output_factory=controller_factory,
            frame_source_factory=frame_factory,
            serial_name=self.global_settings.get("serial_device"),
            capture_name=self.global_settings.get("capture_device"),
            baudrate=self.global_settings.get("serial_baud", 9600),
            protocol=protocol,
            notification_handler=notification_handler,
            logger=self.logger,
            settings=self.global_settings.data,
            lifetime_allow_dummy=True,
        )
        if previous_builder is not None:
            previous_builder.shutdown()
        try:
            self.preview_pane.set_frame_source(self.runtime_builder.frame_source_for_preview())
            self.virtual_controller.model.set_controller(
                self.runtime_builder.controller_output_for_manual_input()
            )
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "GUI lifetime Port の更新に失敗しました",
                component="MainWindow",
                event="configuration.invalid",
                exc=exc,
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

        try:
            if self.runtime_builder is not None:
                self.runtime_builder.shutdown()
        except Exception as e:
            self.logger.technical(
                "WARNING",
                "Runtime builder 解放エラー",
                component="MainWindow",
                event="resource.cleanup_failed",
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
