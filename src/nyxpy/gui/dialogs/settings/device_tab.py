"""Device 設定 tab。"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.hardware.swbt.config import supported_controller_models
from nyxpy.framework.core.hardware.swbt.discovery import SwbtAdapterView
from nyxpy.framework.core.hardware.swbt.errors import (
    is_swbt_connect_cancelled,
    swbt_connect_cancel_code,
)
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.gui.background_task import BackgroundTask
from nyxpy.gui.capture_availability import is_ponkan_capture_available
from nyxpy.gui.layout import WINDOW_SIZE_PRESETS, normalize_window_size_preset_key

_CAPTURE_SOURCE_OPTIONS = (
    ("カメラ", "camera"),
    ("ウィンドウ", "window"),
)
_CAPTURE_SOURCE_OPTION = ("キャプチャ", "capture")

type SwbtLifecycleAction = Callable[
    [Callable[[object], None], Callable[[BaseException], None]],
    Callable[[], None] | None,
]


class DeviceSettingsTab(QWidget):
    """Capture device と serial controller の設定 tab。"""

    def __init__(
        self,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        parent=None,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
        ponkan_capture_available: bool | None = None,
        swbt_adapter_provider: Callable[[], tuple[SwbtAdapterView, ...]] | None = None,
        swbt_pair: SwbtLifecycleAction | None = None,
        swbt_reconnect: SwbtLifecycleAction | None = None,
        swbt_disconnect: SwbtLifecycleAction | None = None,
        swbt_status: Callable[[], object | None] | None = None,
        swbt_actions_enabled: bool = True,
    ):
        """Settings store と device discovery service を保持し、選択 UI を作ります。"""
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        self.device_discovery = device_discovery or DeviceDiscoveryService()
        self.swbt_adapter_provider = swbt_adapter_provider
        self.swbt_pair = swbt_pair
        self.swbt_reconnect = swbt_reconnect
        self.swbt_disconnect = swbt_disconnect
        self.swbt_status = swbt_status
        self.swbt_actions_enabled = bool(swbt_actions_enabled)
        self._swbt_busy = False
        self._swbt_connected = False
        self._cancel_swbt_connect: Callable[[], None] | None = None
        self._swbt_connect_operation: str | None = None
        self._background_tasks: set[BackgroundTask] = set()
        self.ponkan_capture_available = (
            is_ponkan_capture_available()
            if ponkan_capture_available is None
            else bool(ponkan_capture_available)
        )
        layout = QVBoxLayout(self)

        self.cap_group = QGroupBox("キャプチャ入力")
        cap_group = self.cap_group
        cap_group_layout = QVBoxLayout(cap_group)
        cap_form = QFormLayout()

        source_row = QHBoxLayout()
        self.capture_source_type = QComboBox()
        for label, value in _CAPTURE_SOURCE_OPTIONS:
            self.capture_source_type.addItem(label, value)
        if self.ponkan_capture_available:
            self.capture_source_type.addItem(*_CAPTURE_SOURCE_OPTION)
        self._set_capture_source_type(self.settings.get("capture_source_type", "camera"))
        self.capture_source_type.currentIndexChanged.connect(
            lambda _index: self._update_source_field_state(self._capture_source_type())
        )
        source_row.addWidget(self.capture_source_type)
        self.aspect_box_enabled = QCheckBox("レターボックス")
        self.aspect_box_enabled.setChecked(
            bool(self.settings.get("capture_aspect_box_enabled", False))
        )
        source_row.addWidget(self.aspect_box_enabled)
        self.source_row = _layout_container(source_row)
        cap_form.addRow(QLabel("Source:"), self.source_row)

        cap_row = QHBoxLayout()
        self.cap_device = QComboBox()
        self.refresh_capture_devices()
        refresh_btn = QPushButton("リロード")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self.refresh_capture_devices)
        cap_row.addWidget(self.cap_device)
        cap_row.addWidget(refresh_btn)
        self.camera_label = QLabel("Camera:")
        self.camera_row = _layout_container(cap_row)
        cap_form.addRow(self.camera_label, self.camera_row)

        window_row = QHBoxLayout()
        self.window_source = QComboBox()
        self.window_source.setEditable(True)
        self.refresh_window_sources()
        refresh_window_btn = QPushButton("リロード")
        refresh_window_btn.setFixedWidth(60)
        refresh_window_btn.clicked.connect(self.refresh_window_sources)
        window_row.addWidget(self.window_source)
        window_row.addWidget(refresh_window_btn)
        self.window_label = QLabel("Window:")
        self.window_row = _layout_container(window_row)
        cap_form.addRow(self.window_label, self.window_row)

        self.window_match_mode = QComboBox()
        self.window_match_mode.addItems(["exact", "contains"])
        self.window_match_mode.setCurrentText(
            self.settings.get("capture_window_match_mode", "exact")
        )
        self.window_match_label = QLabel("Window Match:")
        cap_form.addRow(self.window_match_label, self.window_match_mode)

        self.capture_backend = QComboBox()
        self.capture_backend.addItems(["auto", "mss", "windows_graphics_capture"])
        self.capture_backend.setCurrentText(self.settings.get("capture_backend", "auto"))
        self.backend_label = QLabel("Backend:")
        cap_form.addRow(self.backend_label, self.capture_backend)

        self.capture_fps = QComboBox()
        self.capture_fps.addItem("source default", None)
        for fps in ("15", "30", "60"):
            self.capture_fps.addItem(fps, float(fps))
        current_capture_fps = self.settings.get("capture_fps", None)
        if current_capture_fps not in (None, 0, 0.0):
            self.capture_fps.setCurrentText(str(int(float(current_capture_fps))))
        self.capture_fps_label = QLabel("Capture FPS:")
        cap_form.addRow(self.capture_fps_label, self.capture_fps)

        self.n3dsxl_hd_aspect_box_enabled = QCheckBox("有効")
        self.n3dsxl_hd_aspect_box_enabled.setChecked(
            bool(self.settings.get("n3dsxl_hd_aspect_box_enabled", True))
        )
        self.n3dsxl_hd_aspect_box_enabled_label = QLabel("HD Aspect Box:")
        cap_form.addRow(
            self.n3dsxl_hd_aspect_box_enabled_label,
            self.n3dsxl_hd_aspect_box_enabled,
        )
        self.capture_setting_rows = (
            (self.n3dsxl_hd_aspect_box_enabled_label, self.n3dsxl_hd_aspect_box_enabled),
        )

        cap_group_layout.addLayout(cap_form)
        layout.addWidget(cap_group)

        self.controller_group = QGroupBox("コントローラー出力")
        controller_group_layout = QVBoxLayout(self.controller_group)
        controller_form = QFormLayout()

        self.controller_backend = QComboBox()
        self.controller_backend.addItem("Serial", "serial")
        self.controller_backend.addItem("swbt", "swbt")
        self._set_controller_backend(self.settings.get("controller.backend", "serial"))
        self.controller_backend.currentIndexChanged.connect(
            lambda _index: self._update_controller_field_state()
        )
        controller_form.addRow(QLabel("Backend:"), self.controller_backend)
        controller_group_layout.addLayout(controller_form)

        self.ser_group = QGroupBox("Serial")
        ser_group = self.ser_group
        ser_group_layout = QVBoxLayout(ser_group)
        ser_form = QFormLayout()

        ser_row = QHBoxLayout()
        self.ser_device = QComboBox()
        self.refresh_serial_devices()
        refresh_ser_btn = QPushButton("リロード")
        refresh_ser_btn.setFixedWidth(60)
        refresh_ser_btn.clicked.connect(self.refresh_serial_devices)
        ser_row.addWidget(self.ser_device)
        ser_row.addWidget(refresh_ser_btn)
        ser_form.addRow(QLabel("Device:"), ser_row)

        self.ser_protocol = QComboBox()
        protocol_options = ProtocolFactory.get_protocol_names()
        self.ser_protocol.addItems(protocol_options)
        current_protocol = self.settings.get("controller.serial.protocol", "")
        if current_protocol in protocol_options:
            self.ser_protocol.setCurrentText(current_protocol)
        self.ser_protocol.currentTextChanged.connect(self._apply_protocol_default_baud)

        self.ser_baud = QComboBox()
        baud_options = [
            "1200",
            "2400",
            "4800",
            "9600",
            "14400",
            "19200",
            "38400",
            "57600",
            "115200",
        ]
        self.ser_baud.addItems(baud_options)
        current_baud = str(self.settings.get("controller.serial.baudrate", 9600))
        if current_baud in baud_options:
            self.ser_baud.setCurrentText(current_baud)
        else:
            self.ser_baud.setCurrentText("9600")
        ser_form.addRow(QLabel("Protocol:"), self.ser_protocol)
        ser_form.addRow(QLabel("Baud Rate:"), self.ser_baud)
        ser_group_layout.addLayout(ser_form)
        controller_group_layout.addWidget(ser_group)

        self.swbt_group = QGroupBox("swbt")
        swbt_group_layout = QVBoxLayout(self.swbt_group)
        swbt_form = QFormLayout()

        self.swbt_controller_type = QComboBox()
        for model in supported_controller_models():
            self.swbt_controller_type.addItem(model.display_name, model.settings_value)
        self._set_combo_data(
            self.swbt_controller_type,
            self.settings.get("controller.swbt.controller_type", "pro-controller"),
        )
        swbt_form.addRow(QLabel("Controller:"), self.swbt_controller_type)

        adapter_row = QHBoxLayout()
        self.swbt_adapter = QComboBox()
        self.swbt_adapter.setEditable(True)
        saved_adapter = str(self.settings.get("controller.swbt.adapter", "") or "")
        self.swbt_adapter.setCurrentIndex(-1)
        self.swbt_adapter.setEditText(saved_adapter)
        adapter_editor = self.swbt_adapter.lineEdit()
        if adapter_editor is not None:
            adapter_editor.textChanged.connect(lambda _text: self._update_controller_field_state())
        self.refresh_swbt_btn = QPushButton("リロード")
        self.refresh_swbt_btn.setFixedWidth(60)
        self.refresh_swbt_btn.clicked.connect(self.refresh_swbt_adapters)
        adapter_row.addWidget(self.swbt_adapter)
        adapter_row.addWidget(self.refresh_swbt_btn)
        swbt_form.addRow(QLabel("Adapter:"), adapter_row)

        self.swbt_key_store = QComboBox()
        self.swbt_key_store.setEditable(True)
        current_key_store = str(self.settings.get("controller.swbt.key_store_path", "") or "")
        for key_store_path in self._swbt_key_store_candidates(current_key_store):
            self.swbt_key_store.addItem(key_store_path, key_store_path)
        self.swbt_key_store.setCurrentText(current_key_store or self._default_swbt_key_store_path())
        self.swbt_controller_type.currentIndexChanged.connect(
            self._update_swbt_key_store_for_controller
        )
        swbt_form.addRow(QLabel("Key Store:"), self.swbt_key_store)

        lifecycle_row = QHBoxLayout()
        self.swbt_pair_btn = QPushButton("Pair")
        self.swbt_reconnect_btn = QPushButton("Reconnect")
        self.swbt_disconnect_btn = QPushButton("Disconnect")
        self.swbt_pair_btn.clicked.connect(self._pair_swbt)
        self.swbt_reconnect_btn.clicked.connect(self._reconnect_swbt)
        self.swbt_disconnect_btn.clicked.connect(self._disconnect_swbt)
        lifecycle_row.addWidget(self.swbt_pair_btn)
        lifecycle_row.addWidget(self.swbt_reconnect_btn)
        lifecycle_row.addWidget(self.swbt_disconnect_btn)
        swbt_form.addRow(QLabel("Connection:"), lifecycle_row)

        self.swbt_status_label = QLabel("disconnected")
        swbt_form.addRow(QLabel("Status:"), self.swbt_status_label)
        swbt_group_layout.addLayout(swbt_form)
        controller_group_layout.addWidget(self.swbt_group)
        layout.addWidget(self.controller_group)

        self.appearance_group = QGroupBox("外観", self)
        appearance_group = self.appearance_group
        appearance_layout = QVBoxLayout(appearance_group)
        appearance_form = QFormLayout()
        self.window_size_preset = QComboBox(self)
        for preset in WINDOW_SIZE_PRESETS:
            self.window_size_preset.addItem(preset.label, preset.key)
        current_key = normalize_window_size_preset_key(
            self.settings.get("gui.window_size_preset", "full_hd")
        )
        self.window_size_preset.setCurrentIndex(self.window_size_preset.findData(current_key))
        appearance_form.addRow(QLabel("ウィンドウサイズ:"), self.window_size_preset)
        fps_options = ["15", "30", "60"]
        self.preview_fps = QComboBox()
        self.preview_fps.addItems(fps_options)
        current_preview_fps = str(self.settings.get("preview_fps", 60))
        if current_preview_fps in fps_options:
            self.preview_fps.setCurrentText(current_preview_fps)
        appearance_form.addRow(QLabel("Preview FPS:"), self.preview_fps)
        appearance_layout.addLayout(appearance_form)
        layout.addWidget(appearance_group)
        layout.addStretch(1)

        self.refresh_swbt_adapters()
        if self._controller_backend() == "swbt":
            self._refresh_swbt_status()
        self._update_source_field_state(self._capture_source_type())
        self._update_controller_field_state()

    def _apply_protocol_default_baud(self, protocol_name: str):
        default_baud = str(ProtocolFactory.get_default_baudrate(protocol_name))
        if self.ser_baud.findText(default_baud) < 0:
            self.ser_baud.addItem(default_baud)
        self.ser_baud.setCurrentText(default_baud)

    def refresh_capture_devices(self):
        devices = self.device_discovery.detect(timeout_sec=2.0).capture_names()
        self.cap_device.clear()
        self.cap_device.addItems(devices)
        current_cap = self.settings.get("capture_device", "")
        if current_cap in devices:
            self.cap_device.setCurrentText(current_cap)

    def refresh_window_sources(self):
        current_identifier = str(self.settings.get("capture_window_identifier", "") or "")
        current_title = self.settings.get("capture_window_title", "")
        self.window_source.clear()
        windows = self.device_discovery.detect_window_sources(timeout_sec=2.0)
        for window in windows:
            self.window_source.addItem(
                window.display_name,
                {
                    "title": window.title,
                    "identifier": str(window.identifier),
                },
            )
        for index in range(self.window_source.count()):
            data = self.window_source.itemData(index) or {}
            if data.get("identifier") == current_identifier or data.get("title") == current_title:
                self.window_source.setCurrentIndex(index)
                return

    def refresh_serial_devices(self):
        serials = self.device_discovery.detect(timeout_sec=2.0).serial_devices
        self.ser_device.clear()
        current_ser = str(self.settings.get("controller.serial.device", "") or "")
        for device in serials:
            self.ser_device.addItem(device.display_name, str(device.identifier))
        for index in range(self.ser_device.count()):
            if self.ser_device.itemData(index) == current_ser:
                self.ser_device.setCurrentIndex(index)
                return

    def refresh_swbt_adapters(self) -> None:
        if self.swbt_adapter_provider is None or self._swbt_busy:
            return
        selected = _editable_combo_value(self.swbt_adapter) or str(
            self.settings.get("controller.swbt.adapter", "") or ""
        )
        self._set_swbt_busy(True)
        self.swbt_status_label.setText("adapter を検索中...")
        task = BackgroundTask(self.swbt_adapter_provider, parent=self)
        task.succeeded.connect(
            lambda adapters: (
                self._replace_swbt_adapters(tuple(adapters), selected) if isValid(self) else None
            )
        )
        task.failed.connect(
            lambda error: self._on_swbt_adapter_refresh_failed(error) if isValid(self) else None
        )
        task.finished.connect(lambda: self._set_swbt_busy(False) if isValid(self) else None)
        self._track_background_task(task)
        task.start()

    def _replace_swbt_adapters(
        self,
        adapters: tuple[SwbtAdapterView, ...],
        selected: str,
    ) -> None:
        self.swbt_adapter.clear()
        for adapter in adapters:
            self.swbt_adapter.addItem(adapter.display_name, adapter.name)
        alias_matches = [
            adapter
            for adapter in adapters
            if selected == adapter.name or selected in adapter.aliases
        ]
        if len(alias_matches) == 1:
            selected = alias_matches[0].name
        selected_index = self.swbt_adapter.findData(selected) if selected else -1
        self.swbt_adapter.setCurrentIndex(selected_index)
        if selected_index < 0:
            self.swbt_adapter.setEditText(selected)
        if adapters:
            self.swbt_status_label.setText(f"adapter {len(adapters)} 件")
        else:
            self.swbt_status_label.setText("利用可能な swbt adapter がありません")

    def _on_swbt_adapter_refresh_failed(self, error: BaseException) -> None:
        self.swbt_status_label.setText(f"adapter refresh failed: {error}")

    def _track_background_task(self, task: BackgroundTask) -> None:
        self._background_tasks.add(task)
        task.finished.connect(lambda: self._finish_background_task(task) if isValid(self) else None)

    def _finish_background_task(self, task: BackgroundTask) -> None:
        self._background_tasks.discard(task)
        task.deleteLater()

    def apply(self):
        source_type = self._capture_source_type()
        self.settings.set("capture_source_type", source_type)
        if source_type == "camera":
            self.settings.set("capture_device", self.cap_device.currentText())
            self.settings.set("capture_fps", self.capture_fps.currentData())
            self.settings.set("capture_aspect_box_enabled", self.aspect_box_enabled.isChecked())
        elif source_type == "window":
            window_data = self.window_source.currentData() or {}
            window_title = self.window_source.currentText().strip()
            selected_title = str(window_data.get("title", ""))
            selected_identifier = str(window_data.get("identifier", ""))
            if window_title != selected_title:
                selected_identifier = ""
            self.settings.set("capture_window_title", window_title or selected_title)
            self.settings.set("capture_window_identifier", selected_identifier)
            self.settings.set("capture_window_match_mode", self.window_match_mode.currentText())
            self.settings.set("capture_backend", self.capture_backend.currentText())
            self.settings.set("capture_fps", self.capture_fps.currentData())
            self.settings.set("capture_aspect_box_enabled", self.aspect_box_enabled.isChecked())
        elif source_type == "capture":
            self.settings.set("capture_provider", "ponkan")
            self.settings.set("capture_device_profile", "n3dsxl")
            self.settings.set(
                "n3dsxl_hd_aspect_box_enabled",
                self.n3dsxl_hd_aspect_box_enabled.isChecked(),
            )
        self.settings.set("preview_fps", int(self.preview_fps.currentText()))
        self.settings.set("controller.backend", self._controller_backend())
        self.settings.set(
            "controller.serial.device",
            self.ser_device.currentData() or self.ser_device.currentText(),
        )
        self.settings.set("controller.serial.protocol", self.ser_protocol.currentText())
        self.settings.set("controller.serial.baudrate", int(self.ser_baud.currentText()))
        self._save_swbt_settings()
        self.settings.set("gui.window_size_preset", self.window_size_preset.currentData())

    def _save_swbt_settings(self, *, select_backend: bool = False) -> None:
        if select_backend:
            self.settings.set("controller.backend", "swbt")
        self.settings.set(
            "controller.swbt.controller_type",
            self.swbt_controller_type.currentData() or self.swbt_controller_type.currentText(),
        )
        swbt_adapter = _editable_combo_value(self.swbt_adapter)
        self.settings.set("controller.swbt.adapter", swbt_adapter or None)
        swbt_key_store = self.swbt_key_store.currentText().strip()
        self.settings.set("controller.swbt.key_store_path", swbt_key_store or None)

    def _swbt_key_store_candidates(self, current: str) -> tuple[str, ...]:
        candidates = [
            str(model.default_key_store_path()).replace("\\", "/")
            for model in supported_controller_models()
        ]
        config_dir = getattr(self.settings, "config_dir", None)
        if config_dir is not None:
            for path in sorted((Path(config_dir) / "swbt").glob("*.json")):
                candidates.append(f".nyxpy/swbt/{path.name}")
        if current:
            candidates.append(current)
        return tuple(dict.fromkeys(candidates))

    def _default_swbt_key_store_path(self) -> str:
        controller_type = self.swbt_controller_type.currentData()
        for model in supported_controller_models():
            if model.settings_value == controller_type:
                return str(model.default_key_store_path()).replace("\\", "/")
        return ""

    def _update_swbt_key_store_for_controller(self) -> None:
        current = self.swbt_key_store.currentText().strip()
        defaults = {
            str(model.default_key_store_path()).replace("\\", "/")
            for model in supported_controller_models()
        }
        if not current or current in defaults:
            self.swbt_key_store.setCurrentText(self._default_swbt_key_store_path())

    def _capture_source_type(self) -> str:
        value = self.capture_source_type.currentData()
        return str(value or "camera")

    def _controller_backend(self) -> str:
        value = self.controller_backend.currentData()
        return str(value or "serial")

    def _set_capture_source_type(self, value: object) -> None:
        index = self.capture_source_type.findData(str(value or "camera"))
        self.capture_source_type.setCurrentIndex(index if index >= 0 else 0)

    def _set_controller_backend(self, value: object) -> None:
        self._set_combo_data(self.controller_backend, str(value or "serial"))

    def _set_combo_data(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findText(str(value or ""))
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _update_source_field_state(self, source_type: str) -> None:
        is_camera = source_type == "camera"
        is_window = source_type == "window"
        is_capture = source_type == "capture"
        self.camera_label.setVisible(is_camera)
        self.camera_row.setVisible(is_camera)
        self.window_label.setVisible(is_window)
        self.window_row.setVisible(is_window)
        self.window_match_label.setVisible(is_window)
        self.window_match_mode.setVisible(is_window)
        self.backend_label.setVisible(is_window)
        self.capture_backend.setVisible(is_window)
        self.aspect_box_enabled.setVisible(not is_capture)
        self.capture_fps_label.setVisible(not is_capture)
        self.capture_fps.setVisible(not is_capture)
        for label, widget in self.capture_setting_rows:
            label.setVisible(is_capture)
            widget.setVisible(is_capture)

    def _update_controller_field_state(self) -> None:
        is_swbt = self._controller_backend() == "swbt"
        settings_enabled = self.swbt_actions_enabled and not self._swbt_busy
        self.controller_backend.setEnabled(self.swbt_actions_enabled and not self._swbt_busy)
        self.ser_group.setVisible(not is_swbt)
        self.ser_group.setEnabled(settings_enabled)
        self.swbt_group.setVisible(is_swbt)
        self.swbt_group.setEnabled(self.swbt_actions_enabled)
        self.swbt_controller_type.setEnabled(settings_enabled)
        self.swbt_adapter.setEnabled(settings_enabled)
        self.swbt_key_store.setEnabled(settings_enabled)
        adapter_selected = bool(_editable_combo_value(self.swbt_adapter))
        connect_enabled = is_swbt and settings_enabled and adapter_selected
        cancelling_pair = (
            self._cancel_swbt_connect is not None and self._swbt_connect_operation == "pair"
        )
        cancelling_reconnect = (
            self._cancel_swbt_connect is not None and self._swbt_connect_operation == "reconnect"
        )
        self.swbt_pair_btn.setEnabled(cancelling_pair or connect_enabled)
        self.swbt_reconnect_btn.setEnabled(cancelling_reconnect or connect_enabled)
        self.swbt_disconnect_btn.setEnabled(is_swbt and settings_enabled and self._swbt_connected)
        self.refresh_swbt_btn.setEnabled(is_swbt and settings_enabled)

    def _set_swbt_busy(self, busy: bool) -> None:
        self._swbt_busy = bool(busy)
        self._update_controller_field_state()

    @property
    def swbt_lifecycle_busy(self) -> bool:
        """Pair/Reconnect/Disconnectの完了待ちかを返す。"""
        return getattr(self, "_swbt_lifecycle_running", False)

    def _pair_swbt(self) -> None:
        self._save_swbt_settings(select_backend=True)
        self._start_or_cancel_swbt_connect("pair", self.swbt_pair)

    def _reconnect_swbt(self) -> None:
        self._save_swbt_settings(select_backend=True)
        self._start_or_cancel_swbt_connect("reconnect", self.swbt_reconnect)

    def _start_or_cancel_swbt_connect(
        self,
        operation: str,
        action: SwbtLifecycleAction | None,
    ) -> None:
        if self._cancel_swbt_connect is not None and self._swbt_connect_operation == operation:
            self._cancel_swbt_connect()
            self._cancel_swbt_connect = None
            button = self.swbt_pair_btn if operation == "pair" else self.swbt_reconnect_btn
            button.setText("Cancelling...")
            button.setEnabled(False)
            self.swbt_status_label.setText(
                "pairing をキャンセル中..."
                if operation == "pair"
                else "reconnect をキャンセル中..."
            )
            return
        self._run_swbt_lifecycle(action, connect_operation=operation)

    def _disconnect_swbt(self) -> None:
        self._run_swbt_lifecycle(self.swbt_disconnect, disconnect=True)

    def _run_swbt_lifecycle(
        self,
        action: SwbtLifecycleAction | None,
        *,
        disconnect: bool = False,
        connect_operation: str | None = None,
    ) -> None:
        if action is None:
            self.swbt_status_label.setText("swbt lifecycle is unavailable")
            return
        self._set_swbt_busy(True)
        self._swbt_lifecycle_running = True
        self.swbt_status_label.setText("disconnecting..." if disconnect else "connecting...")

        def succeeded(status: object) -> None:
            if not isValid(self):
                return
            if disconnect:
                self._swbt_connected = False
                self.swbt_status_label.setText("disconnected")
            else:
                self._set_swbt_status(status)
            self._swbt_lifecycle_running = False
            self._reset_swbt_connect_action()
            self._set_swbt_busy(False)

        def failed(error: BaseException) -> None:
            if not isValid(self):
                return
            self._swbt_connected = False
            if connect_operation is not None and is_swbt_connect_cancelled(error):
                self.swbt_status_label.setText(
                    "再接続をキャンセルしました"
                    if swbt_connect_cancel_code(error) == "NYX_SWBT_RECONNECT_CANCELLED"
                    else "ペアリングをキャンセルしました"
                )
            else:
                operation = "disconnect" if disconnect else "connection"
                self.swbt_status_label.setText(f"{operation} failed: {error}")
            self._swbt_lifecycle_running = False
            self._reset_swbt_connect_action()
            self._set_swbt_busy(False)

        try:
            cancel = action(succeeded, failed)
            if (
                connect_operation is not None
                and self._swbt_lifecycle_running
                and cancel is not None
            ):
                self._cancel_swbt_connect = cancel
                self._swbt_connect_operation = connect_operation
                button = (
                    self.swbt_pair_btn if connect_operation == "pair" else self.swbt_reconnect_btn
                )
                button.setText("Cancel")
                self._update_controller_field_state()
        except Exception as exc:
            failed(exc)

    def _reset_swbt_connect_action(self) -> None:
        self._cancel_swbt_connect = None
        self._swbt_connect_operation = None
        self.swbt_pair_btn.setText("Pair")
        self.swbt_reconnect_btn.setText("Reconnect")

    def _refresh_swbt_status(self) -> None:
        if self.swbt_status is None:
            return
        if self._controller_backend() != "swbt":
            self.swbt_status_label.setText("disconnected")
            return
        try:
            self._set_swbt_status(self.swbt_status())
        except Exception as exc:
            self.swbt_status_label.setText(f"status failed: {exc}")

    def _set_swbt_status(self, status: object | None) -> None:
        if status is None:
            self._swbt_connected = False
            self.swbt_status_label.setText("disconnected")
            self._update_controller_field_state()
            return
        self._swbt_connected = bool(getattr(status, "connected", False))
        message = str(getattr(status, "message", "connected"))
        controller_type = str(getattr(status, "controller_type", ""))
        adapter = str(getattr(status, "adapter", ""))
        if self._swbt_connected and adapter:
            adapter_index = self.swbt_adapter.findData(adapter)
            self.swbt_adapter.setCurrentIndex(adapter_index)
            if adapter_index < 0:
                self.swbt_adapter.setEditText(adapter)
        parts = [message]
        if controller_type:
            parts.append(controller_type)
        if adapter:
            parts.append(adapter)
        self.swbt_status_label.setText(" / ".join(parts))
        self._update_controller_field_state()


def _layout_container(layout: QHBoxLayout) -> QWidget:
    container = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    container.setLayout(layout)
    return container


def _editable_combo_value(combo: QComboBox) -> str:
    text = combo.currentText().strip()
    index = combo.currentIndex()
    if index >= 0 and text == combo.itemText(index):
        return str(combo.itemData(index) or text).strip()
    return text
