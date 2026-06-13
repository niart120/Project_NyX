"""Device 設定 tab。"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nyxpy.framework.core.hardware.device_discovery import DeviceDiscoveryService
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.framework.core.settings.global_settings import GlobalSettings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings
from nyxpy.gui.layout import WINDOW_SIZE_PRESETS, normalize_window_size_preset_key

_CAPTURE_SOURCE_OPTIONS = (
    ("カメラ", "camera"),
    ("ウィンドウ", "window"),
    ("キャプチャ", "capture"),
)


class DeviceSettingsTab(QWidget):
    """Capture device と serial controller の設定 tab。"""

    def __init__(
        self,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        parent=None,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
    ):
        """Settings store と device discovery service を保持し、選択 UI を作ります。"""
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        self.device_discovery = device_discovery or DeviceDiscoveryService()
        layout = QVBoxLayout(self)

        self.cap_group = QGroupBox("キャプチャ入力")
        cap_group = self.cap_group
        cap_group_layout = QVBoxLayout(cap_group)
        cap_form = QFormLayout()

        source_row = QHBoxLayout()
        self.capture_source_type = QComboBox()
        for label, value in _CAPTURE_SOURCE_OPTIONS:
            self.capture_source_type.addItem(label, value)
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

        self.capture_provider = QComboBox()
        self.capture_provider.addItem("ponkan", "ponkan")
        _set_combo_current_data(
            self.capture_provider,
            self.settings.get("capture_provider", "ponkan"),
        )
        self.capture_provider_label = QLabel("Capture Provider:")
        cap_form.addRow(self.capture_provider_label, self.capture_provider)

        self.capture_device_profile = QComboBox()
        self.capture_device_profile.addItem("n3dsxl", "n3dsxl")
        _set_combo_current_data(
            self.capture_device_profile,
            self.settings.get("capture_device_profile", "n3dsxl"),
        )
        self.capture_device_profile_label = QLabel("Device Profile:")
        cap_form.addRow(self.capture_device_profile_label, self.capture_device_profile)

        self.ponkan_backend = QComboBox()
        for backend in ("auto", "d3xx", "d3xx-native"):
            self.ponkan_backend.addItem(backend, backend)
        _set_combo_current_data(self.ponkan_backend, self.settings.get("ponkan_backend", "auto"))
        self.ponkan_backend_label = QLabel("Ponkan Backend:")
        cap_form.addRow(self.ponkan_backend_label, self.ponkan_backend)

        self.ponkan_raw_slots = QSpinBox()
        self.ponkan_raw_slots.setRange(1, 16)
        self.ponkan_raw_slots.setValue(int(self.settings.get("ponkan_raw_slots", 2)))
        self.ponkan_raw_slots_label = QLabel("Raw Slots:")
        cap_form.addRow(self.ponkan_raw_slots_label, self.ponkan_raw_slots)

        self.ponkan_output_queue_size = QSpinBox()
        self.ponkan_output_queue_size.setRange(1, 64)
        self.ponkan_output_queue_size.setValue(
            int(self.settings.get("ponkan_output_queue_size", 2))
        )
        self.ponkan_output_queue_size_label = QLabel("Output Queue Size:")
        cap_form.addRow(self.ponkan_output_queue_size_label, self.ponkan_output_queue_size)

        self.ponkan_drop_policy = QComboBox()
        for policy in ("drop_oldest", "drop_newest", "block"):
            self.ponkan_drop_policy.addItem(policy, policy)
        _set_combo_current_data(
            self.ponkan_drop_policy,
            self.settings.get("ponkan_drop_policy", "drop_oldest"),
        )
        self.ponkan_drop_policy_label = QLabel("Drop Policy:")
        cap_form.addRow(self.ponkan_drop_policy_label, self.ponkan_drop_policy)

        self.ponkan_poll_interval = QDoubleSpinBox()
        self.ponkan_poll_interval.setDecimals(6)
        self.ponkan_poll_interval.setRange(0.000001, 1.0)
        self.ponkan_poll_interval.setSingleStep(0.001)
        self.ponkan_poll_interval.setValue(float(self.settings.get("ponkan_poll_interval", 0.004)))
        self.ponkan_poll_interval_label = QLabel("Poll Interval:")
        cap_form.addRow(self.ponkan_poll_interval_label, self.ponkan_poll_interval)

        self.ponkan_read_timeout = QDoubleSpinBox()
        self.ponkan_read_timeout.setDecimals(3)
        self.ponkan_read_timeout.setRange(0.0, 60.0)
        self.ponkan_read_timeout.setSingleStep(0.1)
        self.ponkan_read_timeout.setValue(float(self.settings.get("ponkan_read_timeout", 1.0)))
        self.ponkan_read_timeout_label = QLabel("Read Timeout:")
        cap_form.addRow(self.ponkan_read_timeout_label, self.ponkan_read_timeout)

        self.ponkan_collect_timing = QCheckBox("有効")
        self.ponkan_collect_timing.setChecked(
            bool(self.settings.get("ponkan_collect_timing", False))
        )
        self.ponkan_collect_timing_label = QLabel("Collect Timing:")
        cap_form.addRow(self.ponkan_collect_timing_label, self.ponkan_collect_timing)

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
            (self.capture_provider_label, self.capture_provider),
            (self.capture_device_profile_label, self.capture_device_profile),
            (self.ponkan_backend_label, self.ponkan_backend),
            (self.ponkan_raw_slots_label, self.ponkan_raw_slots),
            (self.ponkan_output_queue_size_label, self.ponkan_output_queue_size),
            (self.ponkan_drop_policy_label, self.ponkan_drop_policy),
            (self.ponkan_poll_interval_label, self.ponkan_poll_interval),
            (self.ponkan_read_timeout_label, self.ponkan_read_timeout),
            (self.ponkan_collect_timing_label, self.ponkan_collect_timing),
            (self.n3dsxl_hd_aspect_box_enabled_label, self.n3dsxl_hd_aspect_box_enabled),
        )

        cap_group_layout.addLayout(cap_form)
        layout.addWidget(cap_group)

        ser_group = QGroupBox("シリアルデバイス")
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
        current_protocol = self.settings.get("serial_protocol", "")
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
        current_baud = str(self.settings.get("serial_baud", 9600))
        if current_baud in baud_options:
            self.ser_baud.setCurrentText(current_baud)
        else:
            self.ser_baud.setCurrentText("9600")
        ser_form.addRow(QLabel("Protocol:"), self.ser_protocol)
        ser_form.addRow(QLabel("Baud Rate:"), self.ser_baud)
        ser_group_layout.addLayout(ser_form)
        layout.addWidget(ser_group)

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

        self._update_source_field_state(self._capture_source_type())

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
        current_ser = str(self.settings.get("serial_device", "") or "")
        for device in serials:
            self.ser_device.addItem(device.display_name, str(device.identifier))
        for index in range(self.ser_device.count()):
            if self.ser_device.itemData(index) == current_ser:
                self.ser_device.setCurrentIndex(index)
                return

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
            self.settings.set("capture_provider", self.capture_provider.currentData())
            self.settings.set("capture_device_profile", self.capture_device_profile.currentData())
            self.settings.set("ponkan_backend", self.ponkan_backend.currentData())
            self.settings.set("ponkan_raw_slots", self.ponkan_raw_slots.value())
            self.settings.set(
                "ponkan_output_queue_size",
                self.ponkan_output_queue_size.value(),
            )
            self.settings.set("ponkan_drop_policy", self.ponkan_drop_policy.currentData())
            self.settings.set("ponkan_poll_interval", self.ponkan_poll_interval.value())
            self.settings.set("ponkan_read_timeout", self.ponkan_read_timeout.value())
            self.settings.set("ponkan_collect_timing", self.ponkan_collect_timing.isChecked())
            self.settings.set(
                "n3dsxl_hd_aspect_box_enabled",
                self.n3dsxl_hd_aspect_box_enabled.isChecked(),
            )
        self.settings.set("preview_fps", int(self.preview_fps.currentText()))
        self.settings.set(
            "serial_device",
            self.ser_device.currentData() or self.ser_device.currentText(),
        )
        self.settings.set("serial_protocol", self.ser_protocol.currentText())
        self.settings.set("serial_baud", int(self.ser_baud.currentText()))
        self.settings.set("gui.window_size_preset", self.window_size_preset.currentData())

    def _capture_source_type(self) -> str:
        value = self.capture_source_type.currentData()
        return str(value or "camera")

    def _set_capture_source_type(self, value: object) -> None:
        index = self.capture_source_type.findData(str(value or "camera"))
        self.capture_source_type.setCurrentIndex(index if index >= 0 else 0)

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


def _layout_container(layout: QHBoxLayout) -> QWidget:
    container = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    container.setLayout(layout)
    return container


def _set_combo_current_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    combo.setCurrentIndex(index if index >= 0 else 0)
