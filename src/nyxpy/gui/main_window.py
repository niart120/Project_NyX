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

from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.gui.app_services import GuiAppServices, SettingsApplyOutcome
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog
from nyxpy.gui.panes.control_pane import ControlPane, RunUiState
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane


class MainWindow(QMainWindow):
    def __init__(
        self,
        services: GuiAppServices | None = None,
        *,
        project_root: Path | None = None,
    ):
        super().__init__()
        if services is None:
            self.project_root = Path.cwd() if project_root is None else Path(project_root)
        else:
            self.project_root = (
                Path(project_root) if project_root is not None else services.project_root
            )
        self.services = services or GuiAppServices(project_root=self.project_root)
        self.logging = self.services.logging
        self.logger = self.services.logger
        self.global_settings = self.services.global_settings
        self.secrets_settings = self.services.secrets_settings
        self.device_discovery = self.services.device_discovery
        self.macro_catalog = self.services.macro_catalog
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
        try:
            outcome = self.services.apply_settings(is_run_active=self._is_run_active())
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "GUI settings application failed.",
                component="MainWindow",
                event="configuration.apply_failed",
                exc=exc,
            )
            self.status_label.setText("設定を反映できません")
            return
        if "preview_fps" in outcome.changed_keys:
            self.preview_pane.preview_fps = self.global_settings.get("preview_fps", 30)
            self.preview_pane.apply_fps()
        if outcome.deferred:
            self.status_label.setText("設定変更は実行完了後に反映されます")
            return
        self._apply_runtime_ports(outcome)

    def execute_macro_immediate(self):
        """即時実行モード：パラメータ入力なしでマクロを実行する"""
        self._start_macro({})  # 空のパラメータ辞書を渡す

    def execute_macro_with_params(self):
        """パラメータ付き実行モード：パラメータ入力ダイアログを表示して実行する"""
        macro_name = self.macro_browser.selected_macro_display_name()
        if macro_name is None:
            self.status_label.setText("マクロが選択されていません")
            return
        dlg = MacroParamsDialog(self, macro_name)
        if dlg.exec() != QDialog.Accepted:
            return

        # パラメータを解析して実行に渡す
        params = dlg.param_edit.text()
        try:
            exec_args = parse_define_args(params)
        except Exception as exc:
            self.logger.technical(
                "WARNING",
                "Macro parameter parse failed.",
                component="MainWindow",
                event="macro.params_invalid",
                exc=exc,
            )
            self.status_label.setText("パラメータを解析できません")
            return
        self._start_macro(exec_args)

    def _start_macro(self, exec_args):
        """
        共通のマクロ実行処理

        Args:
            exec_args: マクロに渡す引数辞書
        """
        macro_id = self.macro_browser.selected_macro_id()
        if macro_id is None:
            self.status_label.setText("マクロが選択されていません")
            return
        try:
            builder = self.services.create_runtime_builder()
            self.run_handle = builder.start(
                RuntimeBuildRequest(macro_id=macro_id, entrypoint="gui", exec_args=exec_args)
            )
        except Exception as exc:
            self.run_handle = None
            self.logger.technical(
                "ERROR",
                "Macro start failed.",
                component="MainWindow",
                event="runtime.start_failed",
                exc=exc,
            )
            self.status_label.setText("エラー: マクロを開始できません")
            self.control_pane.set_run_state(RunUiState.FINISHED)
            return
        self.control_pane.set_run_state(RunUiState.RUNNING)
        self.status_label.setText("実行中")
        self._run_poll_timer.start(self.global_settings.get("runtime.gui_poll_interval_ms", 100))

    def _is_run_active(self) -> bool:
        return self.run_handle is not None and not self.run_handle.done()

    def _apply_runtime_ports(self, outcome: SettingsApplyOutcome) -> None:
        if not outcome.builder_replaced:
            return
        try:
            if outcome.frame_source_changed:
                self.preview_pane.pause()
            self.preview_pane.set_frame_source(outcome.preview_frame_source)
            if outcome.frame_source_changed:
                self.preview_pane.resume()
            self.virtual_controller.model.set_controller(outcome.manual_controller)
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
            self.control_pane.set_run_state(RunUiState.CANCELLING)

    def _poll_run_handle(self) -> None:
        if self.run_handle is None or not self.run_handle.done():
            return
        self._run_poll_timer.stop()
        try:
            self.last_run_result = self.run_handle.result()
            status = self._format_run_result(self.last_run_result)
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "Runtime handle result retrieval failed.",
                component="MainWindow",
                event="runtime.result_failed",
                exc=exc,
            )
            status = "エラー: 実行結果を取得できません"
        self.run_handle = None
        self.on_finished(status)
        outcome = self.services.flush_deferred_settings()
        if outcome is not None:
            self._apply_runtime_ports(outcome)

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

        if self.run_handle is not None and not self.run_handle.done():
            self.run_handle.cancel()
            if not self.run_handle.wait(self.services.close_wait_timeout_sec):
                self.logger.technical(
                    "WARNING",
                    "Runtime handle の終了がタイムアウトしました",
                    component="MainWindow",
                    event="macro.cancelled",
                )

        self.preview_pane.pause()
        self.log_pane.dispose()
        self.services.close()
        super().closeEvent(event)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.control_pane.set_run_state(RunUiState.FINISHED)

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
