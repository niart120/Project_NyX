from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
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
from nyxpy.gui.layout import (
    DEFAULT_WINDOW_SIZE_PRESET_KEY,
    WINDOW_SIZE_PRESETS,
    layout_metrics_for_key,
    normalize_window_size_preset_key,
    window_size_preset_for_key,
)
from nyxpy.gui.panes.control_pane import ControlPane, RunUiState
from nyxpy.gui.panes.log_pane import LogPane
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.gui.panes.preview_pane import PreviewPane
from nyxpy.gui.panes.virtual_controller_pane import VirtualControllerPane

_UNBOUNDED_WIDGET_HEIGHT = 16777215


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
        self.preview_connection_error: BaseException | None = None
        self.manual_controller_error: BaseException | None = None
        self.window_size_actions: dict[str, QAction] = {}
        self.window_size_action_group: QActionGroup | None = None
        self.current_window_size_preset_key = normalize_window_size_preset_key(
            self.global_settings.get(
                "gui.window_size_preset",
                DEFAULT_WINDOW_SIZE_PRESET_KEY,
            )
        )
        if (
            self.global_settings.get("gui.window_size_preset")
            != self.current_window_size_preset_key
        ):
            self.global_settings.set("gui.window_size_preset", self.current_window_size_preset_key)
        self._run_poll_timer = QTimer(self)
        self._run_poll_timer.timeout.connect(self._poll_run_handle)
        self.setup_ui()
        QTimer.singleShot(100, self.deferred_init)

    def deferred_init(self):
        """Perform initialization that can be deferred until after UI appears"""
        self.setup_connections()  # Setup signal connections between UI components
        self.apply_app_settings()

    def _build_menu_bar(self) -> None:
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_app_settings)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(settings_action)

        view_menu = self.menuBar().addMenu("表示")
        self.window_size_action_group = QActionGroup(self)
        self.window_size_action_group.setExclusive(True)
        for preset in WINDOW_SIZE_PRESETS:
            action = QAction(preset.label, self)
            action.setCheckable(True)
            action.setData(preset.key)
            action.triggered.connect(
                lambda checked=False, key=preset.key: self.apply_window_size_preset(key)
            )
            self.window_size_action_group.addAction(action)
            self.window_size_actions[preset.key] = action
            view_menu.addAction(action)

    def apply_window_size_preset(self, key: object, *, save: bool = True) -> None:
        preset_key = normalize_window_size_preset_key(key)
        preset = window_size_preset_for_key(preset_key)
        self.current_window_size_preset_key = preset_key
        self.current_layout_metrics = layout_metrics_for_key(preset_key)
        self.setFixedSize(preset.window_width, preset.window_height)
        self._apply_layout_metrics_to_panes()
        action = self.window_size_actions.get(preset_key)
        if action is not None:
            action.setChecked(True)
        if save and self.global_settings.get("gui.window_size_preset") != preset_key:
            self.global_settings.set("gui.window_size_preset", preset_key)

    def setup_ui(self):
        self.setWindowTitle("NyxPy GUI")
        self._build_menu_bar()
        self.apply_window_size_preset(self.current_window_size_preset_key, save=False)

        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(central)

        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.macro_browser = MacroBrowserPane(self.macro_catalog, self)
        self.control_pane = ControlPane(self)
        self.macro_explorer_panel = QWidget(self)
        macro_panel_layout = QVBoxLayout(self.macro_explorer_panel)
        macro_panel_layout.setContentsMargins(0, 0, 0, 0)
        macro_panel_layout.addWidget(self.macro_browser, 1)
        macro_panel_layout.addWidget(self.control_pane, 0)
        left_layout.addWidget(self.macro_explorer_panel, 1)

        self.virtual_controller = VirtualControllerPane(self.logger, self)
        left_layout.addWidget(self.virtual_controller, 0)
        main_layout.addWidget(self.left_container)

        self.center_container = QWidget(self)
        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_pane = PreviewPane(
            parent=self.center_container,
            preview_fps=self.global_settings.get("preview_fps", 30),
        )
        center_layout.addWidget(
            self.preview_pane,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        self.preview_tool_log_pane = LogPane(
            self.logging.dispatcher,
            self.center_container,
            title="ツールログ",
            kind="tool",
        )
        center_layout.addWidget(
            self.preview_tool_log_pane,
            1,
            Qt.AlignmentFlag.AlignHCenter,
        )
        main_layout.addWidget(self.center_container)

        self.log_pane = LogPane(
            self.logging.dispatcher,
            self,
            title="マクロログ",
            kind="macro",
        )
        main_layout.addWidget(self.log_pane)

        # status bar
        self.status_label = QLabel("準備中...")
        self.statusBar().addWidget(self.status_label)
        self.capture_status_label = QLabel(self)
        self.serial_status_label = QLabel(self)
        self.statusBar().addPermanentWidget(self.capture_status_label)
        self.statusBar().addPermanentWidget(self.serial_status_label)
        self._apply_layout_metrics_to_panes()
        self._update_connection_status()

    def _apply_layout_metrics_to_panes(self) -> None:
        if not hasattr(self, "left_container"):
            return
        metrics = self.current_layout_metrics
        preset = window_size_preset_for_key(self.current_window_size_preset_key)
        left_width = metrics.allocated_left_width(preset)
        macro_log_width = metrics.allocated_macro_log_width(preset)
        self.centralWidget().layout().setContentsMargins(
            metrics.margin,
            metrics.margin,
            metrics.margin,
            metrics.margin,
        )
        self.centralWidget().layout().setSpacing(metrics.gap)
        self.left_container.setFixedWidth(left_width)
        self.left_container.setMinimumHeight(metrics.center_height)
        self.left_container.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.left_container.layout().setSpacing(metrics.gap)
        self.macro_explorer_panel.layout().setSpacing(metrics.gap)
        self.macro_explorer_panel.setFixedWidth(left_width)
        self.macro_explorer_panel.setMinimumHeight(metrics.macro_explorer_height)
        self.macro_explorer_panel.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.macro_browser.setMinimumHeight(
            min(metrics.macro_explorer_min_height, metrics.macro_explorer_height)
        )
        self.virtual_controller.apply_layout_size(left_width, metrics.controller_height)
        self.center_container.setFixedWidth(metrics.preview_width)
        self.center_container.setMinimumHeight(metrics.center_height)
        self.center_container.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.center_container.layout().setSpacing(metrics.gap)
        self.preview_pane.set_fixed_preview_size(metrics.preview_width, metrics.preview_height)
        self.preview_tool_log_pane.setFixedWidth(metrics.preview_width)
        self.preview_tool_log_pane.setMinimumHeight(metrics.preview_tool_log_min_height)
        self.preview_tool_log_pane.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.log_pane.setFixedWidth(macro_log_width)
        self.log_pane.setMinimumSize(metrics.macro_log_min_width, metrics.macro_log_min_height)
        self.log_pane.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)

    def _update_connection_status(self) -> None:
        source_type = self.global_settings.get("capture_source_type", "camera")
        if source_type == "window":
            capture_name = self.global_settings.get("capture_window_title", "") or "window capture"
        elif source_type == "screen_region":
            capture_name = "screen region"
        else:
            capture_name = self.global_settings.get("capture_device", "")
        if self.preview_connection_error is not None:
            capture_status = f"映像: 接続失敗 ({self.preview_connection_error})"
        else:
            capture_status = f"映像: {capture_name} 接続中" if capture_name else "映像: 未接続"
        serial_name = self.global_settings.get("serial_device", "")
        if self.manual_controller_error is not None:
            serial_status = f"シリアル: 接続失敗 ({self.manual_controller_error})"
        else:
            serial_status = f"シリアル: {serial_name} 接続中" if serial_name else "シリアル: 未接続"
        self.capture_status_label.setText(capture_status)
        self.serial_status_label.setText(serial_status)

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
            self.status_label.setText(f"設定を反映できません: {exc}")
            return
        if "preview_fps" in outcome.changed_keys:
            self.preview_pane.preview_fps = self.global_settings.get("preview_fps", 30)
            self.preview_pane.apply_fps()
        if "gui.window_size_preset" in outcome.changed_keys:
            self.apply_window_size_preset(
                self.global_settings.get("gui.window_size_preset", DEFAULT_WINDOW_SIZE_PRESET_KEY),
                save=False,
            )
        if outcome.deferred:
            self.status_label.setText("設定変更は実行完了後に反映されます")
            return
        self._apply_runtime_ports(outcome)
        self._update_connection_status()

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
        self.preview_connection_error = outcome.preview_error
        self.manual_controller_error = outcome.manual_controller_error
        try:
            if outcome.frame_source_changed or outcome.preview_error is not None:
                self.preview_pane.pause()
            self.preview_pane.set_frame_source(
                None if outcome.preview_error is not None else outcome.preview_frame_source
            )
            if outcome.frame_source_changed and outcome.preview_error is None:
                self.preview_pane.resume()
            self.virtual_controller.model.set_controller(
                None if outcome.manual_controller_error is not None else outcome.manual_controller
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
        self.preview_tool_log_pane.dispose()
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
