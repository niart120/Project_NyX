"""NyX GUI の main window。"""

from dataclasses import dataclass
from pathlib import Path
from threading import Event

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

from nyxpy.framework.core.hardware.capture_source import WindowCaptureSourceConfig
from nyxpy.framework.core.hardware.device_discovery import (
    DUMMY_DEVICE_NAME,
    DeviceDiscoveryResult,
    DeviceInfo,
    WindowDiscoveryResult,
)
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.swbt.errors import (
    is_swbt_connect_cancelled,
    swbt_connect_cancel_code,
)
from nyxpy.framework.core.hardware.window_discovery import WindowInfo, resolve_window
from nyxpy.framework.core.io.ports import ControllerOutputPort
from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from nyxpy.framework.core.runtime.device_selection import (
    ConnectionFallbackReason,
    ConnectionRequest,
    ConnectionResolveStatus,
    ResolvedConnection,
    select_capture_target,
    select_serial_target,
    select_window_target,
)
from nyxpy.framework.core.runtime.exec_args import parse_define_args
from nyxpy.framework.core.runtime.handle import RunHandle
from nyxpy.framework.core.runtime.result import RunResult, RunStatus
from nyxpy.framework.core.settings.schema import SettingValue
from nyxpy.gui.app_services import GuiAppServices, SettingsApplyOutcome
from nyxpy.gui.background_task import BackgroundTask
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


@dataclass(frozen=True, slots=True)
class _SwbtLifecycleResult:
    settings_outcome: SettingsApplyOutcome
    status: object
    manual_controller: ControllerOutputPort


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
        self._swbt_lifecycle_busy = False
        self._macro_starting = False
        self._manual_controller_restoring = False
        self._manual_controller_restore_backend: str | None = None
        self._close_pending = False
        self._background_tasks: set[BackgroundTask] = set()
        self.window_size_actions: dict[str, QAction] = {}
        self.window_size_action_group: QActionGroup | None = None
        self.connection_menu: QMenu | None = None
        self.controller_backend_menu: QMenu | None = None
        self.capture_input_menu: QMenu | None = None
        self.serial_device_menu: QMenu | None = None
        self.protocol_menu: QMenu | None = None
        self.capture_source_type_menu: QMenu | None = None
        self.camera_source_menu: QMenu | None = None
        self.window_source_menu: QMenu | None = None
        self.capture_source_menu: QMenu | None = None
        self.capture_provider_menu: QMenu | None = None
        self.capture_settings_menu: QMenu | None = None
        self.ponkan_backend_menu: QMenu | None = None
        self.capture_fps_menu: QMenu | None = None
        self.serial_baud_menu: QMenu | None = None
        self.capture_device_action_group: QActionGroup | None = None
        self.capture_profile_action_group: QActionGroup | None = None
        self.ponkan_backend_action_group: QActionGroup | None = None
        self.capture_fps_action_group: QActionGroup | None = None
        self.controller_backend_action_group: QActionGroup | None = None
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
        self.controller_backend_menu = self.connection_menu.addMenu("コントローラー")
        self.serial_device_menu = self.connection_menu.addMenu("シリアルデバイス")
        self.protocol_menu = self.connection_menu.addMenu("プロトコル")
        self.connection_menu.aboutToShow.connect(
            lambda: self._refresh_connection_menu(refresh_discovery=True)
        )
        self._refresh_connection_menu()

        view_menu = self.menuBar().addMenu("表示")
        self.window_size_action_group = QActionGroup(self)
        self.window_size_action_group.setExclusive(True)
        for preset in WINDOW_SIZE_PRESETS:
            action = QAction(preset.label, self)
            action.setCheckable(True)
            action.setData(preset.key)
            action.triggered.connect(
                lambda _checked=False, key=preset.key: self.apply_window_size_preset(key)
            )
            self.window_size_action_group.addAction(action)
            self.window_size_actions[preset.key] = action
            view_menu.addAction(action)

    def _refresh_connection_menu(self, *, refresh_discovery: bool = False) -> None:
        snapshot = _device_discovery_snapshot(
            self.device_discovery,
            refresh=refresh_discovery,
        )
        windows = _window_discovery_snapshot(
            self.device_discovery,
            refresh=refresh_discovery,
        )
        if self.capture_input_menu is not None:
            self._populate_capture_input_menu(
                self.capture_input_menu,
                snapshot.capture_devices,
                windows,
            )
        if self.controller_backend_menu is not None:
            self._populate_controller_backend_menu(self.controller_backend_menu)
        if self.serial_device_menu is not None:
            self._populate_serial_device_menu(self.serial_device_menu, snapshot.serial_devices)
        if self.protocol_menu is not None:
            self._populate_protocol_menu(self.protocol_menu)
        is_serial = self.global_settings.get("controller.backend", "serial") == "serial"
        if self.serial_device_menu is not None:
            self.serial_device_menu.setEnabled(is_serial)
        if self.protocol_menu is not None:
            self.protocol_menu.setEnabled(is_serial)

    def _ponkan_capture_available(self) -> bool:
        value = getattr(self.services, "ponkan_capture_available", False)
        if callable(value):
            return bool(value())
        return bool(value)

    def _populate_controller_backend_menu(self, menu: QMenu) -> None:
        menu.clear()
        self.controller_backend_action_group = QActionGroup(self)
        self.controller_backend_action_group.setExclusive(True)
        current = str(self.global_settings.get("controller.backend", "serial") or "serial")
        for label, backend in (("Serial", "serial"), ("swbt", "swbt")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(backend)
            action.setChecked(current == backend)
            action.setEnabled(
                not self._is_run_active()
                and not self._swbt_lifecycle_busy
                and not self._manual_controller_restoring
            )
            action.triggered.connect(
                lambda _checked=False, value=backend: self._apply_connection_settings(
                    {"controller.backend": value}
                )
            )
            self.controller_backend_action_group.addAction(action)
            menu.addAction(action)
        menu.addSeparator()
        adapter_selected = bool(self.global_settings.get("controller.swbt.adapter"))
        lifecycle_enabled = (
            current == "swbt"
            and not self._is_run_active()
            and not self._swbt_lifecycle_busy
            and not self._manual_controller_restoring
        )
        pair_action = QAction("Pair", self)
        reconnect_action = QAction("Reconnect", self)
        disconnect_action = QAction("Disconnect", self)
        pair_action.setEnabled(lifecycle_enabled and adapter_selected)
        reconnect_action.setEnabled(lifecycle_enabled and adapter_selected)
        disconnect_action.setEnabled(lifecycle_enabled and self._swbt_is_connected())
        pair_action.triggered.connect(lambda _checked=False: self._invoke_swbt_action("pair"))
        reconnect_action.triggered.connect(
            lambda _checked=False: self._invoke_swbt_action("reconnect")
        )
        disconnect_action.triggered.connect(
            lambda _checked=False: self._invoke_swbt_action("disconnect")
        )
        menu.addAction(pair_action)
        menu.addAction(reconnect_action)
        menu.addAction(disconnect_action)

    def _populate_capture_input_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
        windows: tuple[WindowInfo, ...],
    ) -> None:
        menu.clear()
        self.capture_source_type_menu = QMenu("入力ソース", menu)
        menu.addMenu(self.capture_source_type_menu)
        self._populate_capture_source_type_menu(
            self.capture_source_type_menu,
            devices,
            windows,
        )
        self.capture_settings_menu = None
        self.ponkan_backend_menu = None
        self.ponkan_backend_action_group = None
        menu.addSeparator()
        self.capture_fps_menu = QMenu("FPS", menu)
        self.capture_fps_menu.setEnabled(
            self.global_settings.get("capture_source_type", "camera") != "capture"
        )
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
                lambda _checked=False, fps=value: self._apply_connection_settings(
                    {"capture_fps": fps}
                )
            )
            self.capture_fps_action_group.addAction(action)
            self.capture_fps_menu.addAction(action)

    def _populate_capture_source_type_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
        windows: tuple[WindowInfo, ...],
    ) -> None:
        menu.clear()
        self.camera_source_menu = QMenu("カメラ", menu)
        self.window_source_menu = QMenu("ウィンドウ", menu)
        self.capture_source_menu = None
        self.capture_provider_menu = None
        self.capture_profile_action_group = None
        menu.addMenu(self.camera_source_menu)
        menu.addMenu(self.window_source_menu)
        self._populate_camera_source_menu(self.camera_source_menu, devices)
        self._populate_window_source_menu(self.window_source_menu, windows)
        if self._ponkan_capture_available():
            self.capture_source_menu = QMenu("キャプチャ", menu)
            menu.addMenu(self.capture_source_menu)
            self._populate_direct_capture_source_menu(self.capture_source_menu)

    def _populate_direct_capture_source_menu(self, menu: QMenu) -> None:
        menu.clear()
        self.capture_profile_action_group = QActionGroup(self)
        self.capture_profile_action_group.setExclusive(True)
        action = QAction("N3DSXL (ponkan-python)", self)
        action.setCheckable(True)
        action.setData("n3dsxl")
        action.setChecked(
            self.global_settings.get("capture_source_type", "camera") == "capture"
            and self.global_settings.get("capture_provider", "ponkan") == "ponkan"
            and self.global_settings.get("capture_device_profile", "n3dsxl") == "n3dsxl"
        )
        action.triggered.connect(
            lambda _checked=False: self._apply_connection_settings(
                {
                    "capture_source_type": "capture",
                    "capture_provider": "ponkan",
                    "capture_device_profile": "n3dsxl",
                }
            )
        )
        self.capture_profile_action_group.addAction(action)
        menu.addAction(action)

    def _populate_camera_source_menu(
        self,
        menu: QMenu,
        devices: tuple[DeviceInfo, ...],
    ) -> None:
        menu.clear()
        self.capture_device_action_group = QActionGroup(self)
        self.capture_device_action_group.setExclusive(True)
        current = str(self.global_settings.get("capture_device", "") or "")
        selection = select_capture_target(
            ConnectionRequest(kind="capture", requested=current, allow_dummy=True),
            DeviceDiscoveryResult(capture_devices=devices),
        )
        dummy_action = QAction(DUMMY_DEVICE_NAME, self)
        dummy_action.setCheckable(True)
        dummy_action.setData(DUMMY_DEVICE_NAME)
        dummy_action.setChecked(
            selection.fallback_reason == ConnectionFallbackReason.USER_SELECTED_DUMMY
        )
        dummy_action.triggered.connect(
            lambda _checked=False: self._apply_connection_settings(
                {"capture_source_type": "camera", "capture_device": DUMMY_DEVICE_NAME}
            )
        )
        self.capture_device_action_group.addAction(dummy_action)
        menu.addAction(dummy_action)
        _add_auto_dummy_status_action(menu, selection, self)
        if not devices:
            empty_action = QAction("利用可能なキャプチャ入力なし", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        for device in devices:
            action = QAction(device.display_name, self)
            action.setCheckable(True)
            action.setData(device.name)
            action.setChecked(selection.selected == device)
            action.triggered.connect(
                lambda _checked=False, name=device.name: self._apply_connection_settings(
                    {"capture_source_type": "camera", "capture_device": name}
                )
            )
            self.capture_device_action_group.addAction(action)
            menu.addAction(action)

    def _populate_window_source_menu(
        self,
        menu: QMenu,
        windows: tuple[WindowInfo, ...],
    ) -> None:
        group = QActionGroup(self)
        group.setExclusive(True)
        selection = _select_window_connection_status(self.global_settings, windows)
        _add_auto_dummy_status_action(menu, selection, self)
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
            action.setChecked(selection.selected == window)
            action.triggered.connect(
                lambda _checked=False, selected=window: self._apply_connection_settings(
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
        current = str(self.global_settings.get("controller.serial.device", "") or "")
        selection = select_serial_target(
            ConnectionRequest(kind="serial", requested=current, allow_dummy=True),
            DeviceDiscoveryResult(serial_devices=devices),
        )
        dummy_action = QAction(DUMMY_DEVICE_NAME, self)
        dummy_action.setCheckable(True)
        dummy_action.setData(DUMMY_DEVICE_NAME)
        dummy_action.setChecked(
            selection.fallback_reason == ConnectionFallbackReason.USER_SELECTED_DUMMY
        )
        dummy_action.triggered.connect(
            lambda _checked=False: self._apply_connection_settings(
                {
                    "controller.backend": "serial",
                    "controller.serial.device": DUMMY_DEVICE_NAME,
                }
            )
        )
        self.serial_device_action_group.addAction(dummy_action)
        menu.addAction(dummy_action)
        _add_auto_dummy_status_action(menu, selection, self)
        if not devices:
            empty_action = QAction("利用可能なシリアルデバイスなし", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        for device in devices:
            identifier = str(device.identifier)
            action = QAction(device.display_name, self)
            action.setCheckable(True)
            action.setData(identifier)
            action.setChecked(selection.selected == device)
            action.triggered.connect(
                lambda _checked=False, serial=identifier: self._apply_connection_settings(
                    {
                        "controller.backend": "serial",
                        "controller.serial.device": serial,
                    }
                )
            )
            self.serial_device_action_group.addAction(action)
            menu.addAction(action)
        menu.addSeparator()
        self.serial_baud_menu = QMenu("ボーレート", menu)
        menu.addMenu(self.serial_baud_menu)
        self.serial_baud_action_group = QActionGroup(self)
        self.serial_baud_action_group.setExclusive(True)
        current_baud = str(self.global_settings.get("controller.serial.baudrate", 9600))
        protocol_name = str(
            self.global_settings.get("controller.serial.protocol", "CH552") or "CH552"
        )
        baud_options = [str(value) for value in _supported_baudrates(protocol_name)]
        if current_baud not in baud_options:
            baud_options.append(current_baud)
        for baud in baud_options:
            action = QAction(baud, self)
            action.setCheckable(True)
            action.setData(int(baud))
            action.setChecked(baud == current_baud)
            action.triggered.connect(
                lambda _checked=False, value=int(baud): self._apply_connection_settings(
                    {
                        "controller.backend": "serial",
                        "controller.serial.baudrate": value,
                    }
                )
            )
            self.serial_baud_action_group.addAction(action)
            self.serial_baud_menu.addAction(action)

    def _populate_protocol_menu(self, menu: QMenu) -> None:
        menu.clear()
        self.protocol_action_group = QActionGroup(self)
        self.protocol_action_group.setExclusive(True)
        current = str(self.global_settings.get("controller.serial.protocol", "CH552") or "CH552")
        for protocol_name in ProtocolFactory.get_protocol_names():
            action = QAction(protocol_name, self)
            action.setCheckable(True)
            action.setData(protocol_name)
            action.setChecked(protocol_name == current)
            action.triggered.connect(
                lambda _checked=False, name=protocol_name: self._apply_connection_settings(
                    _protocol_setting_updates(
                        name,
                        self.global_settings.get("controller.serial.baudrate", 9600),
                    )
                )
            )
            self.protocol_action_group.addAction(action)
            menu.addAction(action)

    def _apply_connection_settings(self, updates: dict[str, SettingValue]) -> None:
        if (
            _controller_settings_changed(frozenset(updates)) or "controller.backend" in updates
        ) and (
            self._is_run_active() or self._swbt_lifecycle_busy or self._manual_controller_restoring
        ):
            self.status_label.setText("実行中または接続操作中はコントローラー設定を変更できません")
            return
        for key, value in updates.items():
            if self.global_settings.get(key) != value:
                self.global_settings.set(key, value)
        self.apply_app_settings()
        self._refresh_connection_menu()

    def _invoke_swbt_action(self, action: str) -> None:
        if action == "pair":
            self._pair_swbt_controller_async()
        elif action == "reconnect":
            self._reconnect_swbt_controller_async()
        elif action == "disconnect":
            self._disconnect_swbt_controller_async()

    def _pair_swbt_controller(self) -> object:
        return self._connect_swbt_manual_controller("pair")

    def _reconnect_swbt_controller(self) -> object:
        return self._connect_swbt_manual_controller("reconnect")

    def _disconnect_swbt_controller(self) -> None:
        if self._is_run_active():
            raise RuntimeError("macro is running")
        if not self._release_manual_controller(
            event="swbt.manual_controller_release_failed",
            message="GUI manual controller release failed before swbt disconnect.",
            user_message="エラー: swbt 切断前に手動入力用コントローラーを解放できません",
        ):
            raise RuntimeError("manual controller release failed")
        try:
            self.services.disconnect_swbt()
        except Exception as exc:
            self.manual_controller_error = exc
            self.logger.technical(
                "ERROR",
                "swbt disconnect failed.",
                component="MainWindow",
                event="swbt.disconnect_failed",
                exc=exc,
            )
            self.status_label.setText("エラー: swbt を切断できません")
            self._update_connection_status()
            raise
        self.manual_controller_error = None
        self.virtual_controller.model.set_controller(None)
        self._sync_manual_input_state()
        self._update_connection_status()

    def _connect_swbt_manual_controller(self, operation: str) -> object:
        if self._is_run_active():
            raise RuntimeError("macro is running")
        if not self._release_manual_controller(
            event="swbt.manual_controller_release_failed",
            message="GUI manual controller release failed before swbt connect.",
            user_message="エラー: swbt 接続前に手動入力用コントローラーを解放できません",
        ):
            raise RuntimeError("manual controller release failed")
        try:
            canonicalize = getattr(self.services, "canonicalize_swbt_adapter", None)
            config = canonicalize() if callable(canonicalize) else None
            outcome = self.services.apply_settings(is_run_active=False)
            self._apply_runtime_ports(outcome)
            status = self._call_swbt_lifecycle(operation, config)
            builder = self.services.create_runtime_builder()
            manual_controller = builder.controller_output_for_manual_input()
        except Exception as exc:
            self.manual_controller_error = exc
            self.virtual_controller.model.set_controller(None)
            self.logger.technical(
                "ERROR",
                "swbt lifecycle operation failed.",
                component="MainWindow",
                event="swbt.lifecycle_failed",
                exc=exc,
            )
            self.status_label.setText("エラー: swbt 接続操作に失敗しました")
            self._update_connection_status()
            raise
        self.manual_controller_error = None
        self.virtual_controller.model.set_controller(manual_controller)
        self._sync_manual_input_state()
        self._update_connection_status()
        return status

    def _pair_swbt_controller_async(self, succeeded=None, failed=None):
        return self._start_swbt_connect_task("pair", succeeded, failed)

    def _reconnect_swbt_controller_async(self, succeeded=None, failed=None):
        return self._start_swbt_connect_task("reconnect", succeeded, failed)

    def _disconnect_swbt_controller_async(self, succeeded=None, failed=None) -> None:
        prepared, previous = self._prepare_swbt_lifecycle(failed, operation="disconnect")
        if not prepared:
            return
        task = BackgroundTask(
            lambda: self._execute_swbt_disconnect(previous),
            parent=self,
        )
        task.succeeded.connect(
            lambda release_error: self._finish_swbt_disconnect(
                release_error,
                succeeded,
                failed,
            )
        )
        task.failed.connect(
            lambda error: self._fail_swbt_lifecycle(error, failed, operation="disconnect")
        )
        self._track_background_task(task)
        task.start()

    def _start_swbt_connect_task(self, operation: str, succeeded, failed):
        prepared, previous = self._prepare_swbt_lifecycle(failed, operation="connect")
        if not prepared:
            return None
        cancellation_event = Event()
        task = BackgroundTask(
            lambda: self._execute_swbt_connect(
                operation,
                previous,
                cancellation_event=cancellation_event,
            ),
            parent=self,
        )
        task.succeeded.connect(lambda result: self._finish_swbt_connect(result, succeeded, failed))
        task.failed.connect(
            lambda error: self._fail_swbt_lifecycle(error, failed, operation="connect")
        )
        self._track_background_task(task)
        task.start()
        return cancellation_event.set

    def _prepare_swbt_lifecycle(
        self,
        failed,
        *,
        operation: str,
    ) -> tuple[bool, ControllerOutputPort | None]:
        if self._is_run_active() or self._swbt_lifecycle_busy or self._manual_controller_restoring:
            error = RuntimeError(
                "macro is running, swbt lifecycle is busy, or controller restore is pending"
            )
            self._notify_async_callback(failed, error)
            return False, None
        if self.global_settings.get("controller.backend", "serial") != "swbt":
            error = RuntimeError("swbt backend is not selected")
            self._notify_async_callback(failed, error)
            return False, None
        if operation == "connect" and not self.global_settings.get("controller.swbt.adapter"):
            error = RuntimeError("swbt adapter is not selected")
            self.status_label.setText("エラー: swbt adapter を選択してください")
            self._notify_async_callback(failed, error)
            return False, None
        previous = self._detach_manual_controller()
        self._swbt_lifecycle_busy = True
        self.status_label.setText(
            "swbt 接続操作中..." if operation == "connect" else "swbt 切断中..."
        )
        self._sync_manual_input_state()
        self._refresh_connection_menu()
        return True, previous

    def _execute_swbt_connect(
        self,
        operation: str,
        previous: ControllerOutputPort | None,
        *,
        cancellation_event: Event | None = None,
    ) -> _SwbtLifecycleResult:
        try:
            self._close_detached_manual_controller(previous)
            canonicalize = getattr(self.services, "canonicalize_swbt_adapter", None)
            config = canonicalize() if callable(canonicalize) else None
            outcome = self.services.apply_settings(is_run_active=False)
            status = self._call_swbt_lifecycle(
                operation,
                config,
                cancellation_event=cancellation_event,
            )
            builder = self.services.create_runtime_builder()
            manual_controller = builder.controller_output_for_manual_input()
            if manual_controller is None:
                raise RuntimeError("swbt manual controller was not created")
            return _SwbtLifecycleResult(outcome, status, manual_controller)
        except Exception as exc:
            try:
                self.services.disconnect_swbt()
            except Exception as cleanup_error:
                raise ExceptionGroup(
                    "swbt connect and cleanup failed",
                    [exc, cleanup_error],
                ) from exc
            raise

    def _call_swbt_lifecycle(
        self,
        operation: str,
        config: object | None,
        *,
        cancellation_event: Event | None = None,
    ) -> object:
        prepared = getattr(self.services, f"{operation}_swbt_prepared", None)
        if callable(prepared) and config is not None:
            if operation in {"pair", "reconnect"}:
                return prepared(config, cancellation_event=cancellation_event)
            return prepared(config)
        return getattr(self.services, f"{operation}_swbt")()

    def _execute_swbt_disconnect(
        self,
        previous: ControllerOutputPort | None,
    ) -> Exception | None:
        release_error: Exception | None = None
        try:
            self._close_detached_manual_controller(previous)
        except Exception as exc:
            release_error = exc
        try:
            self.services.disconnect_swbt()
        except Exception as disconnect_error:
            if release_error is not None:
                raise ExceptionGroup(
                    "swbt disconnect failed",
                    [release_error, disconnect_error],
                ) from disconnect_error
            raise
        return release_error

    def _finish_swbt_connect(self, result: _SwbtLifecycleResult, succeeded, failed) -> None:
        try:
            self._apply_runtime_ports(result.settings_outcome)
            self.manual_controller_error = None
            self.virtual_controller.model.set_controller(result.manual_controller)
            self._swbt_lifecycle_busy = False
            self.status_label.setText("swbt 接続完了")
            self._sync_manual_input_state()
            self._update_connection_status()
            self._refresh_connection_menu()
        except Exception as exc:
            self._fail_swbt_lifecycle(exc, failed, operation="connect")
            return
        self._notify_async_callback(succeeded, result.status)

    def _finish_swbt_disconnect(
        self,
        release_error: BaseException | None,
        succeeded,
        failed,
    ) -> None:
        try:
            if release_error is not None:
                self.logger.technical(
                    "WARNING",
                    "Detached manual controller cleanup failed before successful swbt disconnect.",
                    component="MainWindow",
                    event="swbt.manual_controller_release_retried",
                    exc=release_error,
                )
            self.manual_controller_error = None
            self.virtual_controller.model.set_controller(None)
            self._swbt_lifecycle_busy = False
            self.status_label.setText("swbt を切断しました")
            self._sync_manual_input_state()
            self._update_connection_status()
            self._refresh_connection_menu()
        except Exception as exc:
            self._fail_swbt_lifecycle(exc, failed, operation="disconnect")
            return
        self._notify_async_callback(succeeded, None)

    def _fail_swbt_lifecycle(self, error: BaseException, failed, *, operation: str) -> None:
        if operation == "connect" and is_swbt_connect_cancelled(error):
            self.manual_controller_error = None
            self.virtual_controller.model.set_controller(None)
            self._swbt_lifecycle_busy = False
            error_code = swbt_connect_cancel_code(error)
            self.status_label.setText(
                "swbt 再接続をキャンセルしました"
                if error_code == "NYX_SWBT_RECONNECT_CANCELLED"
                else "swbt ペアリングをキャンセルしました"
            )
            self._sync_manual_input_state()
            self._update_connection_status()
            self._refresh_connection_menu()
            self._notify_async_callback(failed, error)
            return
        self.manual_controller_error = error
        self.virtual_controller.model.set_controller(None)
        self._swbt_lifecycle_busy = False
        self.logger.technical(
            "ERROR",
            "swbt lifecycle operation failed.",
            component="MainWindow",
            event="swbt.lifecycle_failed",
            exc=error,
        )
        self.status_label.setText(
            "エラー: swbt を切断できません"
            if operation == "disconnect"
            else "エラー: swbt 接続操作に失敗しました"
        )
        self._sync_manual_input_state()
        self._update_connection_status()
        self._refresh_connection_menu()
        self._notify_async_callback(failed, error)

    def _notify_async_callback(self, callback, value: object) -> None:
        if callback is None:
            return
        try:
            callback(value)
        except RuntimeError:
            # 設定 dialog がworker完了前に破棄された場合は通知先がない。
            return

    def _track_background_task(self, task: BackgroundTask) -> None:
        self._background_tasks.add(task)
        task.finished.connect(lambda: self._finish_background_task(task))

    def _finish_background_task(self, task: BackgroundTask) -> None:
        self._background_tasks.discard(task)
        task.deleteLater()
        if self._close_pending and not self._background_tasks:
            QTimer.singleShot(0, self.close)

    def _swbt_is_connected(self) -> bool:
        try:
            status = self.services.swbt_status()
        except Exception:
            return False
        return bool(status is not None and status.connected)

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
        self.virtual_controller.model.inputFailed.connect(self._handle_manual_input_failure)
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
        self._sync_manual_input_state()
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
        discovery_snapshot = _device_discovery_snapshot(self.device_discovery)
        if source_type == "window":
            window_snapshot = _window_discovery_snapshot(self.device_discovery)
            capture_selection = _select_window_connection_status(
                self.global_settings,
                window_snapshot,
            )
        elif source_type == "capture":
            capture_selection = None
        else:
            capture_selection = select_capture_target(
                ConnectionRequest(
                    kind="capture",
                    requested=str(self.global_settings.get("capture_device", "") or ""),
                    allow_dummy=True,
                ),
                discovery_snapshot,
            )
        if self.preview_connection_error is not None:
            capture_status = f"映像: 接続失敗 ({self.preview_connection_error})"
        elif source_type == "capture":
            capture_status = "映像: キャプチャ (N3DSXL) 接続中"
        else:
            assert capture_selection is not None
            capture_status = _format_connection_status("映像", capture_selection)
        controller_backend = str(self.global_settings.get("controller.backend", "serial"))
        if controller_backend == "swbt":
            if self.manual_controller_error is not None:
                serial_status = f"swbt: 接続失敗 ({self.manual_controller_error})"
            else:
                serial_status = self._format_swbt_connection_status()
        else:
            serial_selection = select_serial_target(
                ConnectionRequest(
                    kind="serial",
                    requested=str(self.global_settings.get("controller.serial.device", "") or ""),
                    allow_dummy=True,
                ),
                discovery_snapshot,
            )
            if self.manual_controller_error is not None:
                serial_status = f"シリアル: 接続失敗 ({self.manual_controller_error})"
            else:
                serial_status = _format_connection_status("シリアル", serial_selection)
        self.capture_status_label.setText(capture_status)
        self.serial_status_label.setText(serial_status)

    def _format_swbt_connection_status(self) -> str:
        try:
            status = self.services.swbt_status()
        except Exception as exc:
            return f"swbt: 状態取得失敗 ({exc})"
        if status is None:
            return "swbt: 未接続"
        message = status.message or ("connected" if status.connected else "disconnected")
        suffix = f" ({status.adapter})" if status.adapter else ""
        if status.connected:
            return f"swbt: {status.controller_type} 接続中{suffix}"
        return f"swbt: {message}{suffix}"

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
        if self._swbt_lifecycle_busy or self._macro_starting or self._manual_controller_restoring:
            self.status_label.setText("接続操作またはマクロ開始処理の完了後に設定を開いてください")
            return
        dlg = AppSettingsDialog(
            self,
            self.global_settings,
            self.secrets_settings,
            device_discovery=self.device_discovery,
            ponkan_capture_available=self._ponkan_capture_available(),
            swbt_adapter_provider=self.services.refresh_swbt_adapters,
            swbt_pair=self._pair_swbt_controller_async,
            swbt_reconnect=self._reconnect_swbt_controller_async,
            swbt_disconnect=self._disconnect_swbt_controller_async,
            swbt_status=self.services.swbt_status,
            swbt_actions_enabled=not self._is_run_active(),
        )
        dlg.settings_applied.connect(self.apply_app_settings)
        dlg.exec()

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
        self._sync_manual_input_state()
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
        dlg = MacroParamsDialog(self)
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
        if self._swbt_lifecycle_busy or self._macro_starting or self._manual_controller_restoring:
            self.status_label.setText("接続操作中または開始処理中はマクロを開始できません")
            return
        self.virtual_controller.set_manual_input_enabled(False)
        request = RuntimeBuildRequest(macro_id=macro_id, entrypoint="gui", exec_args=exec_args)
        previous = self._detach_manual_controller()
        self._macro_starting = True
        self.control_pane.set_run_state(RunUiState.STARTING)
        self.status_label.setText("マクロ開始準備中")
        task = BackgroundTask(
            lambda: self._start_macro_worker(request, previous),
            parent=self,
        )
        task.succeeded.connect(self._finish_macro_start)
        task.failed.connect(self._fail_macro_start)
        self._track_background_task(task)
        task.start()

    def _start_macro_worker(
        self,
        request: RuntimeBuildRequest,
        previous: ControllerOutputPort | None,
    ) -> RunHandle:
        self._close_detached_manual_controller(previous)
        if self.global_settings.get("controller.backend", "serial") == "swbt":
            canonicalize = getattr(self.services, "canonicalize_swbt_adapter", None)
            if callable(canonicalize):
                canonicalize()
            self.services.apply_settings(is_run_active=False)
        return self.services.create_runtime_builder().start(request)

    def _finish_macro_start(self, handle: RunHandle) -> None:
        self._macro_starting = False
        self.run_handle = handle
        self.control_pane.set_run_state(RunUiState.RUNNING)
        self.status_label.setText("実行中")
        self._run_poll_timer.start(self.global_settings.get("runtime.gui_poll_interval_ms", 100))

    def _fail_macro_start(self, error: BaseException) -> None:
        self._macro_starting = False
        self.run_handle = None
        self.logger.technical(
            "ERROR",
            "Macro start failed.",
            component="MainWindow",
            event="runtime.start_failed",
            exc=error,
        )
        self.status_label.setText("エラー: マクロを開始できません")
        self.control_pane.set_run_state(RunUiState.FINISHED)
        self._sync_manual_input_state()
        self._restore_manual_controller()

    def _is_run_active(self) -> bool:
        return self._macro_starting or (self.run_handle is not None and not self.run_handle.done())

    def _apply_runtime_ports(self, outcome: SettingsApplyOutcome) -> None:
        if not outcome.builder_replaced:
            return
        self.preview_connection_error = outcome.preview_error
        self.manual_controller_error = outcome.manual_controller_error
        try:
            if (
                outcome.frame_source_changed
                or outcome.preview_error is not None
                or outcome.preview_frame_source is not None
            ):
                if outcome.frame_source_changed or outcome.preview_error is not None:
                    self.preview_pane.pause()
                self.preview_pane.set_frame_source(
                    None if outcome.preview_error is not None else outcome.preview_frame_source
                )
                if outcome.frame_source_changed and outcome.preview_error is None:
                    self.preview_pane.resume()
            if (
                outcome.manual_controller_error is not None
                or outcome.manual_controller is not None
                or _controller_settings_changed(outcome.changed_keys)
            ):
                self.virtual_controller.model.set_controller(
                    None
                    if outcome.manual_controller_error is not None
                    else outcome.manual_controller
                )
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "GUI lifetime Port の更新に失敗しました",
                component="MainWindow",
                event="configuration.invalid",
                exc=exc,
            )
        self._sync_manual_input_state()

    def _sync_manual_input_state(self) -> None:
        controller_available = self.virtual_controller.model.controller is not None
        enabled = (
            controller_available and not self._is_run_active() and not self._swbt_lifecycle_busy
        )
        self.virtual_controller.set_manual_input_enabled(enabled)

    def _release_manual_controller(
        self,
        *,
        event: str,
        message: str,
        user_message: str,
    ) -> bool:
        previous = self._detach_manual_controller()
        if previous is None:
            return True
        try:
            self._close_detached_manual_controller(previous)
        except Exception as exc:
            self.manual_controller_error = exc
            self.logger.technical(
                "ERROR",
                message,
                component="MainWindow",
                event=event,
                exc=exc,
            )
            self.status_label.setText(user_message)
            self._update_connection_status()
            return False
        return True

    def _detach_manual_controller(self) -> ControllerOutputPort | None:
        previous = self.virtual_controller.model.controller
        self.virtual_controller.model.set_controller(None)
        self.virtual_controller.model.reset_state()
        self._discard_manual_controller_cache(previous)
        self._sync_manual_input_state()
        return previous

    @staticmethod
    def _close_detached_manual_controller(
        controller: ControllerOutputPort | None,
    ) -> None:
        if controller is None:
            return
        controller.release()
        controller.close()

    def _discard_manual_controller_cache(self, controller) -> None:
        discard = getattr(self.services, "discard_manual_controller", None)
        if callable(discard):
            discard(controller)

    def _handle_manual_input_failure(self, error: BaseException, controller) -> None:
        self._discard_manual_controller_cache(controller)
        self.manual_controller_error = error
        self.status_label.setText(
            "エラー: 手動入力を送信できません。接続を確認して Reconnect してください"
        )
        self._sync_manual_input_state()
        self._update_connection_status()
        task = BackgroundTask(controller.close, parent=self)
        task.failed.connect(self._log_manual_controller_cleanup_failure)
        self._track_background_task(task)
        task.start()

    def _log_manual_controller_cleanup_failure(self, error: BaseException) -> None:
        self.logger.technical(
            "WARNING",
            "Failed manual controller cleanup after input error.",
            component="MainWindow",
            event="controller.cleanup_failed",
            exc=error,
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
        try:
            outcome = self.services.flush_deferred_settings()
        except Exception as exc:
            self.logger.technical(
                "ERROR",
                "Deferred GUI settings application failed.",
                component="MainWindow",
                event="configuration.deferred_apply_failed",
                exc=exc,
            )
            self.status_label.setText(f"実行後の設定を反映できません: {exc}")
            self._sync_manual_input_state()
            self._update_connection_status()
            self._restore_manual_controller()
            return
        if outcome is not None:
            self._apply_runtime_ports(outcome)
            self._update_connection_status()
        self._sync_manual_input_state()
        self._restore_manual_controller()

    def _restore_manual_controller(self) -> None:
        if (
            self.virtual_controller.model.controller is not None
            or self._manual_controller_restoring
            or self._is_run_active()
            or self._close_pending
        ):
            return
        self._manual_controller_restoring = True
        self._manual_controller_restore_backend = str(
            self.global_settings.get("controller.backend", "serial")
        )
        task = BackgroundTask(
            lambda: self.services.create_runtime_builder().controller_output_for_manual_input(),
            parent=self,
        )
        task.succeeded.connect(self._finish_manual_controller_restore)
        task.failed.connect(self._fail_manual_controller_restore)
        self._track_background_task(task)
        task.start()

    def _finish_manual_controller_restore(self, controller: object) -> None:
        restore_backend = self._manual_controller_restore_backend
        self._manual_controller_restoring = False
        self._manual_controller_restore_backend = None
        if not isinstance(controller, ControllerOutputPort):
            self._fail_manual_controller_restore(RuntimeError("manual controller was not created"))
            return
        stale = (
            restore_backend != self.global_settings.get("controller.backend", "serial")
            or self._is_run_active()
            or self._swbt_lifecycle_busy
            or self._close_pending
            or self.virtual_controller.model.controller is not None
        )
        if stale:
            self._discard_manual_controller_cache(controller)
            task = BackgroundTask(
                lambda: self._close_detached_manual_controller(controller),
                parent=self,
            )
            task.failed.connect(self._log_manual_controller_cleanup_failure)
            self._track_background_task(task)
            task.start()
            return
        self.manual_controller_error = None
        self.virtual_controller.model.set_controller(controller)
        self._sync_manual_input_state()
        self._update_connection_status()

    def _fail_manual_controller_restore(self, error: BaseException) -> None:
        self._manual_controller_restoring = False
        self._manual_controller_restore_backend = None
        self.manual_controller_error = error
        self.logger.technical(
            "ERROR",
            "Manual controller restore failed.",
            component="MainWindow",
            event="controller.restore_failed",
            exc=error,
        )
        self._sync_manual_input_state()
        self._update_connection_status()

    def _format_run_result(self, result: RunResult) -> str:
        if result.status is RunStatus.SUCCESS:
            return "完了"
        if result.status is RunStatus.CANCELLED:
            return "中断"
        message = result.error.message if result.error is not None else "不明なエラー"
        return f"エラー: {message}"

    def closeEvent(self, event):
        """ウィンドウ終了時にリソースを確実に解放する。"""
        if self._background_tasks:
            self._close_pending = True
            self.status_label.setText("処理の完了後にアプリケーションを終了します")
            event.ignore()
            return
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
        self._sync_manual_input_state()

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


def _device_discovery_snapshot(
    discovery: object,
    *,
    refresh: bool = False,
) -> DeviceDiscoveryResult:
    if refresh:
        detect = getattr(discovery, "detect", None)
        if callable(detect):
            result = detect(timeout_sec=2.0)
            if isinstance(result, DeviceDiscoveryResult):
                return result
    last_result = getattr(discovery, "last_result", None)
    if isinstance(last_result, DeviceDiscoveryResult):
        return last_result
    return DeviceDiscoveryResult()


def _window_discovery_snapshot(
    discovery: object,
    *,
    refresh: bool = False,
) -> tuple[WindowInfo, ...]:
    if refresh:
        detect_with_result = getattr(discovery, "detect_window_sources_result", None)
        if callable(detect_with_result):
            result = detect_with_result(timeout_sec=2.0)
            if isinstance(result, WindowDiscoveryResult):
                return () if result.failed else result.window_sources
        else:
            detect_windows = getattr(discovery, "detect_window_sources", None)
            if callable(detect_windows):
                windows = detect_windows(timeout_sec=2.0)
                if isinstance(windows, tuple):
                    return windows
    windows = getattr(discovery, "last_window_sources", ())
    if isinstance(windows, tuple):
        return windows
    return ()


def _window_connection_request(settings: object) -> str | None:
    get_setting = getattr(settings, "get")
    identifier = str(get_setting("capture_window_identifier", "") or "").strip()
    if identifier:
        return identifier
    title = str(get_setting("capture_window_title", "") or "").strip()
    return title or None


def _select_window_connection_status(
    settings: object,
    windows: tuple[WindowInfo, ...],
) -> ResolvedConnection:
    get_setting = getattr(settings, "get")
    identifier = str(get_setting("capture_window_identifier", "") or "").strip()
    title = str(get_setting("capture_window_title", "") or "").strip()
    match_mode = str(get_setting("capture_window_match_mode", "exact") or "exact")
    requested = identifier or title or None
    if requested is None:
        return select_window_target(
            ConnectionRequest(kind="window", requested=None, allow_dummy=True),
            windows,
        )
    try:
        selected = resolve_window(
            windows,
            WindowCaptureSourceConfig(
                title_pattern=title,
                identifier=identifier or None,
                match_mode="contains" if match_mode == "contains" else "exact",
            ),
        )
    except ConfigurationError:
        return select_window_target(
            ConnectionRequest(kind="window", requested=requested, allow_dummy=True),
            windows,
        )
    return ResolvedConnection(
        status=ConnectionResolveStatus.SELECTED,
        kind="window",
        requested=requested,
        selected=selected,
    )


def _format_connection_status(label: str, selection: ResolvedConnection) -> str:
    if selection.status == ConnectionResolveStatus.SELECTED and selection.selected is not None:
        return f"{label}: {_selected_display_name(selection.selected)} 接続中"
    if not selection.uses_dummy:
        return f"{label}: 未接続"
    if selection.fallback_reason == ConnectionFallbackReason.USER_SELECTED_DUMMY:
        return f"{label}: ダミーデバイス使用中"
    if selection.fallback_reason == ConnectionFallbackReason.NOT_SELECTED:
        return f"{label}: 未接続 (ダミーデバイス使用中)"
    requested = selection.requested or "未選択"
    return f"{label}: {requested} 未検出 (ダミーデバイス使用中)"


def _add_auto_dummy_status_action(
    menu: QMenu,
    selection: ResolvedConnection,
    parent: QMainWindow,
) -> None:
    if selection.uses_dummy and selection.fallback_reason not in {
        ConnectionFallbackReason.NOT_SELECTED,
        ConnectionFallbackReason.USER_SELECTED_DUMMY,
    }:
        requested = selection.requested or "未選択"
        action = QAction(f"自動フォールバック中: {requested} 未検出", parent)
        action.setEnabled(False)
        menu.addAction(action)


def _selected_display_name(selected: object) -> str:
    display_name = getattr(selected, "display_name", None)
    if display_name:
        return str(display_name)
    title = getattr(selected, "title", None)
    if title:
        return str(title)
    name = getattr(selected, "name", None)
    if name:
        return str(name)
    return str(selected)


def _same_number_or_none(left: object, right: object) -> bool:
    if left in (None, "") and right is None:
        return True
    if left in (None, "") or right is None:
        return False
    try:
        return float(str(left)) == float(str(right))
    except (TypeError, ValueError):
        return False


def _controller_settings_changed(changed_keys: frozenset[str]) -> bool:
    return any(
        key == "controller.backend"
        or key.startswith("controller.serial.")
        or key.startswith("controller.swbt.")
        for key in changed_keys
    )


def _supported_baudrates(protocol_name: str) -> tuple[int, ...]:
    try:
        return ProtocolFactory.get_descriptor(protocol_name).supported_baudrates
    except ValueError:
        return tuple(int(value) for value in _SERIAL_BAUD_OPTIONS)


def _protocol_setting_updates(protocol_name: str, current_baud: object) -> dict[str, SettingValue]:
    descriptor = ProtocolFactory.get_descriptor(protocol_name)
    updates: dict[str, SettingValue] = {
        "controller.backend": "serial",
        "controller.serial.protocol": descriptor.name,
    }
    try:
        baudrate = int(str(current_baud))
    except (TypeError, ValueError):
        baudrate = descriptor.default_baudrate
    if baudrate not in descriptor.supported_baudrates:
        updates["controller.serial.baudrate"] = descriptor.default_baudrate
    return updates
