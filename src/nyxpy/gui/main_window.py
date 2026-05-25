"""NyX GUI の main window。"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryResult, DeviceInfo
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.window_discovery import WindowInfo
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.schema import SettingValue
from nyxpy.framework.core.utils.helper import parse_define_args
from nyxpy.gui.app_services import GuiAppServices, SettingsApplyOutcome
from nyxpy.gui.dialogs.app_settings_dialog import AppSettingsDialog
from nyxpy.gui.dialogs.macro_params_dialog import MacroParamsDialog
from nyxpy.gui.layout import (
    DEFAULT_WINDOW_SIZE_PRESET_KEY,
    LEFT_PANE_CONTENT_MARGIN,
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
from nyxpy.gui.typography import PANE_TITLE_HEIGHT, apply_pane_title_font

_UNBOUNDED_WIDGET_HEIGHT = 16777215
_TOUCH_UNSUPPORTED_STATUS = "現在のプロトコルは 3DS タッチ入力に対応していません"
_PREVIEW_TOUCH_ENABLED_SETTING = "gui.preview_touch_enabled"
_CAPTURE_FPS_OPTIONS = (
    ("source default", None),
    ("15", 15.0),
    ("30", 30.0),
    ("60", 60.0),
)
_SERIAL_BAUD_OPTIONS = (
    "1200",
    "2400",
    "4800",
    "9600",
    "14400",
    "19200",
    "38400",
    "57600",
    "115200",
)


class _VirtualControllerPanel(QWidget):
    def __init__(
        self,
        logger,
        parent: QWidget | None = None,
        *,
        title_indent: int = 0,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(PANE_TITLE_HEIGHT)
        title_layout = QHBoxLayout(self.title_bar)
        self.title_layout = title_layout
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        self.title_label = QLabel("コントローラー", self.title_bar)
        apply_pane_title_font(self.title_label)
        self.title_label.setIndent(title_indent)
        self.touch_panel_checkbox = QCheckBox("タッチパネル", self.title_bar)
        self.touch_panel_checkbox.setFixedHeight(PANE_TITLE_HEIGHT)
        title_layout.addWidget(self.title_label, 0)
        title_layout.addStretch(1)
        title_layout.addWidget(self.touch_panel_checkbox, 0)
        layout.addWidget(self.title_bar, 0)

        self.controller = VirtualControllerPane(logger, self)
        layout.addWidget(
            self.controller,
            1,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._last_controller_size: tuple[int, int] | None = None

    def apply_layout_size(self, width: int, body_height: int) -> None:
        width = max(1, width)
        body_height = max(1, body_height)
        size = (width, body_height)
        if self._last_controller_size == size:
            return
        self._last_controller_size = size
        self.controller.apply_layout_size(width, body_height)

    def relayout_to_current_geometry(self) -> None:
        self.apply_layout_size(self.width(), self.height() - PANE_TITLE_HEIGHT)

    def showEvent(self, event) -> None:
        QTimer.singleShot(0, self.relayout_to_current_geometry)
        super().showEvent(event)

    def resizeEvent(self, event) -> None:
        self.relayout_to_current_geometry()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    """NyX GUI の main window。"""

    def __init__(
        self,
        services: GuiAppServices | None = None,
        *,
        project_root: Path | None = None,
    ):
        """GUI service を準備し、各 pane、menu、signal 接続を初期化します。"""
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
        self._preview_touch_active = False
        self.window_size_actions: dict[str, QAction] = {}
        self.window_size_action_group: QActionGroup | None = None
        self.connection_menu: QMenu | None = None
        self.capture_input_menu: QMenu | None = None
        self.serial_device_menu: QMenu | None = None
        self.protocol_menu: QMenu | None = None
        self.capture_source_type_menu: QMenu | None = None
        self.window_source_menu: QMenu | None = None
        self.capture_fps_menu: QMenu | None = None
        self.serial_baud_menu: QMenu | None = None
        self.capture_device_action_group: QActionGroup | None = None
        self.capture_fps_action_group: QActionGroup | None = None
        self.serial_device_action_group: QActionGroup | None = None
        self.serial_baud_action_group: QActionGroup | None = None
        self.protocol_action_group: QActionGroup | None = None
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
        self.connection_menu = self.menuBar().addMenu("接続")
        self.capture_input_menu = self.connection_menu.addMenu("キャプチャ入力")
        self.serial_device_menu = self.connection_menu.addMenu("シリアルデバイス")
        self.protocol_menu = self.connection_menu.addMenu("プロトコル")
        self.connection_menu.aboutToShow.connect(self._refresh_connection_menu)
        self._refresh_connection_menu()

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

    def _refresh_connection_menu(self) -> None:
        snapshot = _device_discovery_snapshot(self.device_discovery)
        windows = _window_discovery_snapshot(self.device_discovery)
        if self.capture_input_menu is not None:
            self._populate_capture_input_menu(
                self.capture_input_menu,
                snapshot.capture_devices,
                windows,
            )
        if self.serial_device_menu is not None:
            self._populate_serial_device_menu(self.serial_device_menu, snapshot.serial_devices)
        if self.protocol_menu is not None:
            self._populate_protocol_menu(self.protocol_menu)

    def _populate_capture_input_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
        windows: tuple[WindowInfo, ...],
    ) -> None:
        menu.clear()
        self.capture_source_type_menu = QMenu("入力ソース", menu)
        menu.addMenu(self.capture_source_type_menu)
        self._populate_capture_source_type_menu(self.capture_source_type_menu)
        menu.addSeparator()
        self.capture_device_action_group = QActionGroup(self)
        self.capture_device_action_group.setExclusive(True)
        current = str(self.global_settings.get("capture_device", "") or "")
        if not devices:
            empty_action = QAction("利用可能なキャプチャ入力なし", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        for device in devices:
            action = QAction(device.display_name, self)
            action.setCheckable(True)
            action.setData(device.name)
            action.setChecked(device.name == current)
            action.triggered.connect(
                lambda checked=False, name=device.name: self._apply_connection_settings(
                    {"capture_source_type": "camera", "capture_device": name}
                )
            )
            self.capture_device_action_group.addAction(action)
            menu.addAction(action)
        menu.addSeparator()
        self.window_source_menu = QMenu("ウィンドウ", menu)
        menu.addMenu(self.window_source_menu)
        self._populate_window_source_menu(self.window_source_menu, windows)
        menu.addSeparator()
        self.capture_fps_menu = QMenu("FPS", menu)
        menu.addMenu(self.capture_fps_menu)
        self.capture_fps_action_group = QActionGroup(self)
        self.capture_fps_action_group.setExclusive(True)
        current_fps = self.global_settings.get("capture_fps", None)
        for label, value in _CAPTURE_FPS_OPTIONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(value)
            action.setChecked(_same_number_or_none(current_fps, value))
            action.triggered.connect(
                lambda checked=False, fps=value: self._apply_connection_settings(
                    {"capture_fps": fps}
                )
            )
            self.capture_fps_action_group.addAction(action)
            self.capture_fps_menu.addAction(action)

    def _populate_capture_source_type_menu(self, menu: QMenu) -> None:
        group = QActionGroup(self)
        group.setExclusive(True)
        current = str(self.global_settings.get("capture_source_type", "camera") or "camera")
        for source_type, label in (("camera", "カメラ"), ("window", "ウィンドウ")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(source_type)
            action.setChecked(source_type == current)
            action.triggered.connect(
                lambda checked=False, value=source_type: self._apply_connection_settings(
                    {"capture_source_type": value}
                )
            )
            group.addAction(action)
            menu.addAction(action)

    def _populate_window_source_menu(
        self,
        menu: QMenu,
        windows: tuple[WindowInfo, ...],
    ) -> None:
        group = QActionGroup(self)
        group.setExclusive(True)
        current_identifier = str(self.global_settings.get("capture_window_identifier", "") or "")
        current_title = str(self.global_settings.get("capture_window_title", "") or "")
        if not windows:
            empty_action = QAction("利用可能なウィンドウなし", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
            return
        for window in windows:
            identifier = str(window.identifier)
            action = QAction(window.display_name, self)
            action.setCheckable(True)
            action.setData(identifier)
            action.setChecked(identifier == current_identifier or window.title == current_title)
            action.triggered.connect(
                lambda checked=False, selected=window: self._apply_connection_settings(
                    {
                        "capture_source_type": "window",
                        "capture_window_title": selected.title,
                        "capture_window_identifier": str(selected.identifier),
                    }
                )
            )
            group.addAction(action)
            menu.addAction(action)

    def _populate_serial_device_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
    ) -> None:
        menu.clear()
        self.serial_device_action_group = QActionGroup(self)
        self.serial_device_action_group.setExclusive(True)
        current = str(self.global_settings.get("serial_device", "") or "")
        if not devices:
            empty_action = QAction("利用可能なシリアルデバイスなし", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        for device in devices:
            identifier = str(device.identifier)
            action = QAction(device.display_name, self)
            action.setCheckable(True)
            action.setData(identifier)
            action.setChecked(identifier == current)
            action.triggered.connect(
                lambda checked=False, serial=identifier: self._apply_connection_settings(
                    {"serial_device": serial}
                )
            )
            self.serial_device_action_group.addAction(action)
            menu.addAction(action)
        menu.addSeparator()
        self.serial_baud_menu = QMenu("ボーレート", menu)
        menu.addMenu(self.serial_baud_menu)
        self.serial_baud_action_group = QActionGroup(self)
        self.serial_baud_action_group.setExclusive(True)
        current_baud = str(self.global_settings.get("serial_baud", 9600))
        protocol_name = str(self.global_settings.get("serial_protocol", "CH552") or "CH552")
        baud_options = [str(value) for value in _supported_baudrates(protocol_name)]
        if current_baud not in baud_options:
            baud_options.append(current_baud)
        for baud in baud_options:
            action = QAction(baud, self)
            action.setCheckable(True)
            action.setData(int(baud))
            action.setChecked(baud == current_baud)
            action.triggered.connect(
                lambda checked=False, value=int(baud): self._apply_connection_settings(
                    {"serial_baud": value}
                )
            )
            self.serial_baud_action_group.addAction(action)
            self.serial_baud_menu.addAction(action)

    def _populate_protocol_menu(self, menu: QMenu) -> None:
        menu.clear()
        self.protocol_action_group = QActionGroup(self)
        self.protocol_action_group.setExclusive(True)
        current = str(self.global_settings.get("serial_protocol", "CH552") or "CH552")
        for protocol_name in ProtocolFactory.get_protocol_names():
            action = QAction(protocol_name, self)
            action.setCheckable(True)
            action.setData(protocol_name)
            action.setChecked(protocol_name == current)
            action.triggered.connect(
                lambda checked=False, name=protocol_name: self._apply_connection_settings(
                    _protocol_setting_updates(name, self.global_settings.get("serial_baud", 9600))
                )
            )
            self.protocol_action_group.addAction(action)
            menu.addAction(action)

    def _apply_connection_settings(self, updates: dict[str, SettingValue]) -> None:
        for key, value in updates.items():
            if self.global_settings.get(key) != value:
                self.global_settings.set(key, value)
        self.apply_app_settings()
        self._refresh_connection_menu()

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

        self.left_center_container = QWidget()
        left_center_layout = QGridLayout(self.left_center_container)
        left_center_layout.setContentsMargins(0, 0, 0, 0)
        self.macro_browser = MacroBrowserPane(self.macro_catalog, self)
        self.control_pane = ControlPane(
            self,
            horizontal_margin=LEFT_PANE_CONTENT_MARGIN,
        )
        self.macro_explorer_panel = QWidget(self)
        macro_panel_layout = QVBoxLayout(self.macro_explorer_panel)
        macro_panel_layout.setContentsMargins(0, 0, 0, 0)
        macro_panel_layout.addWidget(self.macro_browser, 1)
        macro_panel_layout.addWidget(self.control_pane, 0)
        left_center_layout.addWidget(self.macro_explorer_panel, 0, 0)

        self.virtual_controller_panel = _VirtualControllerPanel(
            self.logger,
            self.left_center_container,
            title_indent=LEFT_PANE_CONTENT_MARGIN,
        )
        self.controller_title_label = self.virtual_controller_panel.title_label
        self.touch_panel_checkbox = self.virtual_controller_panel.touch_panel_checkbox
        self._set_preview_touch_enabled(
            self.global_settings.get(_PREVIEW_TOUCH_ENABLED_SETTING, False),
            save=False,
        )
        self.virtual_controller = self.virtual_controller_panel.controller
        left_center_layout.addWidget(self.virtual_controller_panel, 1, 0)

        self.preview_pane = PreviewPane(
            parent=self.left_center_container,
            preview_fps=self.global_settings.get("preview_fps", 30),
        )
        left_center_layout.addWidget(
            self.preview_pane,
            0,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        self.macro_log_pane = LogPane(
            self.logging.dispatcher,
            self.left_center_container,
            title="マクロログ",
            kind="macro",
            initial_level=self.global_settings.get("logging.gui_level", "INFO"),
        )
        left_center_layout.addWidget(
            self.macro_log_pane,
            1,
            1,
            Qt.AlignmentFlag.AlignLeft,
        )
        main_layout.addWidget(self.left_center_container)

        self.tool_log_pane = LogPane(
            self.logging.dispatcher,
            self,
            title="ツールログ",
            kind="tool",
            initial_level=self.global_settings.get("logging.gui_level", "INFO"),
        )
        main_layout.addWidget(self.tool_log_pane)

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
        if not hasattr(self, "left_center_container"):
            return
        metrics = self.current_layout_metrics
        preset = window_size_preset_for_key(self.current_window_size_preset_key)
        left_width = metrics.allocated_left_width(preset)
        tool_log_width = metrics.allocated_tool_log_width(preset)
        left_center_width = left_width + metrics.gap + metrics.preview_width
        central_widget = self.centralWidget()
        if central_widget is None:
            return
        central_layout = central_widget.layout()
        if central_layout is None:
            return
        central_layout.setContentsMargins(
            metrics.margin,
            0,
            metrics.margin,
            0,
        )
        central_layout.setSpacing(metrics.gap)
        self.left_center_container.setFixedWidth(left_center_width)
        self.left_center_container.setMinimumHeight(metrics.center_height)
        self.left_center_container.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        left_center_layout = self.left_center_container.layout()
        if not isinstance(left_center_layout, QGridLayout):
            return
        left_center_layout.setSpacing(metrics.gap)
        left_center_layout.setColumnMinimumWidth(0, left_width)
        left_center_layout.setColumnMinimumWidth(1, metrics.preview_width)
        left_center_layout.setColumnStretch(0, 0)
        left_center_layout.setColumnStretch(1, 0)
        left_center_layout.setRowMinimumHeight(0, metrics.preview_height)
        left_center_layout.setRowMinimumHeight(1, metrics.bottom_macro_log_min_height)
        left_center_layout.setRowStretch(0, 0)
        left_center_layout.setRowStretch(1, 1)
        macro_explorer_layout = self.macro_explorer_panel.layout()
        if macro_explorer_layout is not None:
            macro_explorer_layout.setSpacing(metrics.gap)
        self.macro_explorer_panel.setFixedSize(left_width, metrics.macro_explorer_height)
        macro_browser_available_height = max(
            0,
            metrics.macro_explorer_height - metrics.gap - self.control_pane.sizeHint().height(),
        )
        self.macro_browser.setMinimumHeight(
            min(metrics.macro_explorer_min_height, macro_browser_available_height)
        )
        self.virtual_controller_panel.setFixedWidth(left_width)
        self.virtual_controller_panel.setMinimumHeight(
            PANE_TITLE_HEIGHT + metrics.bottom_macro_log_min_height
        )
        self.virtual_controller_panel.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.virtual_controller_panel.apply_layout_size(left_width, metrics.bottom_macro_log_height)
        QTimer.singleShot(0, self.virtual_controller_panel.relayout_to_current_geometry)
        self.preview_pane.set_fixed_preview_size(metrics.preview_width, metrics.preview_height)
        self.macro_log_pane.setFixedWidth(metrics.preview_width)
        self.macro_log_pane.setMinimumHeight(metrics.bottom_macro_log_min_height)
        self.macro_log_pane.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)
        self.tool_log_pane.setFixedWidth(tool_log_width)
        self.tool_log_pane.setMinimumSize(metrics.tool_log_min_width, metrics.tool_log_min_height)
        self.tool_log_pane.setMaximumHeight(_UNBOUNDED_WIDGET_HEIGHT)

    def _update_connection_status(self) -> None:
        source_type = self.global_settings.get("capture_source_type", "camera")
        if source_type == "window":
            capture_name = self.global_settings.get("capture_window_title", "") or "window capture"
        else:
            capture_name = self.global_settings.get("capture_device", "")
        if self.preview_connection_error is not None:
            capture_status = f"映像: 接続失敗 ({self.preview_connection_error})"
        else:
            capture_status = f"映像: {capture_name} 接続中" if capture_name else "映像: 未接続"
        serial_name = self._serial_display_name(self.global_settings.get("serial_device", ""))
        if self.manual_controller_error is not None:
            serial_status = f"シリアル: 接続失敗 ({self.manual_controller_error})"
        else:
            serial_status = f"シリアル: {serial_name} 接続中" if serial_name else "シリアル: 未接続"
        self.capture_status_label.setText(capture_status)
        self.serial_status_label.setText(serial_status)

    def _serial_display_name(self, identifier: object) -> str:
        text = str(identifier or "")
        if not text:
            return ""
        display_name = getattr(self.device_discovery, "serial_display_name", None)
        if callable(display_name):
            return str(display_name(text))
        return text

    def setup_connections(self):
        # Connect pane signals fully delegated
        self.macro_browser.selection_changed.connect(self.control_pane.set_selection)
        self.control_pane.run_requested.connect(self.execute_macro_immediate)
        self.control_pane.run_with_params_requested.connect(self.execute_macro_with_params)
        self.control_pane.cancel_requested.connect(self.cancel_macro)
        # Delegate snapshot to PreviewPane and status via signal
        self.control_pane.snapshot_requested.connect(self.preview_pane.take_snapshot)
        self.preview_pane.snapshot_taken.connect(self.status_label.setText)
        self.preview_pane.touch_down_requested.connect(self._handle_preview_touch_down)
        self.preview_pane.touch_move_requested.connect(self._handle_preview_touch_move)
        self.preview_pane.touch_up_requested.connect(self._handle_preview_touch_up)
        self.touch_panel_checkbox.toggled.connect(self._set_preview_touch_enabled)
        self.control_pane.settings_requested.connect(self.open_app_settings)

        # Set status to ready
        self.status_label.setText("準備完了")

    def _set_preview_touch_enabled(self, enabled: bool, *, save: bool = True) -> None:
        enabled = bool(enabled)
        if self.touch_panel_checkbox.isChecked() != enabled:
            self.touch_panel_checkbox.setChecked(enabled)
        if save and self.global_settings.get(_PREVIEW_TOUCH_ENABLED_SETTING) != enabled:
            self.global_settings.set(_PREVIEW_TOUCH_ENABLED_SETTING, enabled)

    def _handle_preview_touch_down(self, x: int, y: int) -> None:
        self._preview_touch_active = False
        if not self.touch_panel_checkbox.isChecked():
            return
        if not self.virtual_controller.model.supports_touch_input():
            self.status_label.setText(_TOUCH_UNSUPPORTED_STATUS)
            return
        self.virtual_controller.model.touch_down(x, y)
        self._preview_touch_active = True

    def _handle_preview_touch_move(self, x: int, y: int) -> None:
        if (
            not self._preview_touch_active
            or not self.touch_panel_checkbox.isChecked()
            or not self.virtual_controller.model.supports_touch_input()
        ):
            return
        self.virtual_controller.model.touch_move(x, y)

    def _handle_preview_touch_up(self) -> None:
        if not self._preview_touch_active:
            return
        self._preview_touch_active = False
        if not self.virtual_controller.model.supports_touch_input():
            return
        self.virtual_controller.model.touch_up()

    def open_app_settings(self):
        dlg = AppSettingsDialog(
            self,
            self.global_settings,
            self.secrets_settings,
            device_discovery=self.device_discovery,
        )
        dlg.settings_applied.connect(self.apply_app_settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
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
        if _PREVIEW_TOUCH_ENABLED_SETTING in outcome.changed_keys:
            self._set_preview_touch_enabled(
                self.global_settings.get(_PREVIEW_TOUCH_ENABLED_SETTING, False),
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
        if dlg.exec() != QDialog.DialogCode.Accepted:
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
        """共通のマクロ実行処理

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
        self.macro_log_pane.dispose()
        self.tool_log_pane.dispose()
        self.services.close()
        super().closeEvent(event)

    def on_finished(self, status: str):
        self.status_label.setText(status)
        self.control_pane.set_run_state(RunUiState.FINISHED)

        if status.startswith("エラー"):
            dlg = QMessageBox(self)
            dlg.setWindowTitle("エラー")
            dlg.setText(f"マクロ実行中にエラーが発生しました:\n{status}")
            dlg.setStandardButtons(
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close
            )
            ret = dlg.exec()
            # リトライまたは閉じるの選択肢を処理
            if ret == QMessageBox.StandardButton.Retry:
                # リトライ時は現在のマクロを再実行
                self._start_macro({})


def _device_discovery_snapshot(discovery: object) -> DeviceDiscoveryResult:
    last_result = getattr(discovery, "last_result", None)
    if isinstance(last_result, DeviceDiscoveryResult):
        return last_result
    return DeviceDiscoveryResult()


def _window_discovery_snapshot(discovery: object) -> tuple[WindowInfo, ...]:
    windows = getattr(discovery, "last_window_sources", ())
    if isinstance(windows, tuple):
        return windows
    return ()


def _same_number_or_none(left: object, right: object) -> bool:
    if left in (None, "") and right is None:
        return True
    if left in (None, "") or right is None:
        return False
    try:
        return float(str(left)) == float(str(right))
    except (TypeError, ValueError):
        return False


def _supported_baudrates(protocol_name: str) -> tuple[int, ...]:
    try:
        return ProtocolFactory.get_descriptor(protocol_name).supported_baudrates
    except ValueError:
        return tuple(int(value) for value in _SERIAL_BAUD_OPTIONS)


def _protocol_setting_updates(protocol_name: str, current_baud: object) -> dict[str, SettingValue]:
    descriptor = ProtocolFactory.get_descriptor(protocol_name)
    updates: dict[str, SettingValue] = {"serial_protocol": descriptor.name}
    try:
        baudrate = int(str(current_baud))
    except (TypeError, ValueError):
        baudrate = descriptor.default_baudrate
    if baudrate not in descriptor.supported_baudrates:
        updates["serial_baud"] = descriptor.default_baudrate
    return updates
