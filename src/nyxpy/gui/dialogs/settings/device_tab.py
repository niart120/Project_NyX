from __future__ import annotations

import inspect

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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


class DeviceSettingsTab(QWidget):
    def __init__(
        self,
        settings: GlobalSettings,
        secrets: SecretsSettings,
        parent=None,
        *,
        device_discovery: DeviceDiscoveryService | None = None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        self.device_discovery = device_discovery or DeviceDiscoveryService()
        layout = QFormLayout(self)

        cap_group = QGroupBox("キャプチャ入力")
        cap_group_layout = QVBoxLayout(cap_group)
        cap_form = QFormLayout()

        self.capture_source_type = QComboBox()
        self.capture_source_type.addItems(["camera", "window", "screen_region"])
        self.capture_source_type.setCurrentText(self.settings.get("capture_source_type", "camera"))
        self.capture_source_type.currentTextChanged.connect(self._update_source_field_state)
        cap_form.addRow(QLabel("Source:"), self.capture_source_type)

        cap_row = QHBoxLayout()
        self.cap_device = QComboBox()
        self.refresh_capture_devices()
        refresh_btn = QPushButton("リロード")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self.refresh_capture_devices)
        cap_row.addWidget(self.cap_device)
        cap_row.addWidget(refresh_btn)
        cap_form.addRow(QLabel("Camera:"), cap_row)

        window_row = QHBoxLayout()
        self.window_source = QComboBox()
        self.window_debug_label = QLabel("")
        self.window_debug_label.setWordWrap(True)
        self.refresh_window_sources()
        refresh_window_btn = QPushButton("リロード")
        refresh_window_btn.setFixedWidth(60)
        refresh_window_btn.clicked.connect(self.refresh_window_sources)
        window_row.addWidget(self.window_source)
        window_row.addWidget(refresh_window_btn)
        cap_form.addRow(QLabel("Window:"), window_row)
        cap_form.addRow(QLabel("Window Debug:"), self.window_debug_label)

        self.window_match_mode = QComboBox()
        self.window_match_mode.addItems(["exact", "contains"])
        self.window_match_mode.setCurrentText(self.settings.get("capture_window_match_mode", "exact"))
        cap_form.addRow(QLabel("Window Match:"), self.window_match_mode)

        self.capture_backend = QComboBox()
        self.capture_backend.addItems(["auto", "mss", "windows_graphics_capture"])
        self.capture_backend.setCurrentText(self.settings.get("capture_backend", "auto"))
        cap_form.addRow(QLabel("Backend:"), self.capture_backend)

        region_row = QHBoxLayout()
        region = self.settings.get("capture_region", {})
        self.region_left = self._region_spinbox(region.get("left", 0) if isinstance(region, dict) else 0)
        self.region_top = self._region_spinbox(region.get("top", 0) if isinstance(region, dict) else 0)
        self.region_width = self._region_spinbox(
            region.get("width", 1280) if isinstance(region, dict) else 1280,
            minimum=1,
        )
        self.region_height = self._region_spinbox(
            region.get("height", 720) if isinstance(region, dict) else 720,
            minimum=1,
        )
        for label, widget in (
            ("L", self.region_left),
            ("T", self.region_top),
            ("W", self.region_width),
            ("H", self.region_height),
        ):
            region_row.addWidget(QLabel(label))
            region_row.addWidget(widget)
        cap_form.addRow(QLabel("Region:"), region_row)

        self.capture_fps = QComboBox()
        self.capture_fps.addItem("source default", None)
        for fps in ("15", "30", "60"):
            self.capture_fps.addItem(fps, float(fps))
        current_capture_fps = self.settings.get("capture_fps", None)
        if current_capture_fps not in (None, 0, 0.0):
            self.capture_fps.setCurrentText(str(int(float(current_capture_fps))))
        cap_form.addRow(QLabel("Capture FPS:"), self.capture_fps)

        self.aspect_box_enabled = QCheckBox("16:9 の黒帯を追加する")
        self.aspect_box_enabled.setChecked(
            bool(self.settings.get("capture_aspect_box_enabled", False))
        )
        cap_form.addRow(QLabel("Aspect Box:"), self.aspect_box_enabled)

        fps_options = ["15", "30", "60"]
        self.preview_fps = QComboBox()
        self.preview_fps.addItems(fps_options)
        current_preview_fps = str(self.settings.get("preview_fps", 60))
        if current_preview_fps in fps_options:
            self.preview_fps.setCurrentText(current_preview_fps)
        cap_form.addRow(QLabel("Preview FPS:"), self.preview_fps)
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

        self._update_source_field_state(self.capture_source_type.currentText())

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
                    "process_id": window.process_id,
                },
            )
        self._update_window_debug_label(windows)
        for index in range(self.window_source.count()):
            data = self.window_source.itemData(index) or {}
            if data.get("identifier") == current_identifier or data.get("title") == current_title:
                self.window_source.setCurrentIndex(index)
                return
        if current_title:
            self.window_source.addItem(
                current_title,
                {
                    "title": current_title,
                    "identifier": current_identifier,
                    "process_id": self.settings.get("capture_window_process_id", None),
                },
            )
            self.window_source.setCurrentIndex(self.window_source.count() - 1)

    def _update_window_debug_label(self, windows) -> None:
        discovery_file = _source_file(self.device_discovery)
        first_title = windows[0].title if windows else "なし"
        diagnostics = ""
        if not windows:
            diagnostics_provider = getattr(self.device_discovery, "window_source_diagnostics", None)
            if callable(diagnostics_provider):
                diagnostics = f" / diag: {diagnostics_provider()}"
        self.window_debug_label.setText(
            f"候補 {len(windows)} 件 / 先頭: {first_title} / discovery: {discovery_file}{diagnostics}"
        )

    def refresh_serial_devices(self):
        serials = self.device_discovery.detect(timeout_sec=2.0).serial_names()
        self.ser_device.clear()
        self.ser_device.addItems(serials)
        current_ser = self.settings.get("serial_device", "")
        if current_ser in serials:
            self.ser_device.setCurrentText(current_ser)

    def apply(self):
        self.settings.set("capture_source_type", self.capture_source_type.currentText())
        self.settings.set("capture_device", self.cap_device.currentText())
        window_data = self.window_source.currentData() or {}
        self.settings.set("capture_window_title", str(window_data.get("title", "")))
        self.settings.set("capture_window_identifier", str(window_data.get("identifier", "")))
        self.settings.set("capture_window_process_id", window_data.get("process_id"))
        self.settings.set("capture_window_match_mode", self.window_match_mode.currentText())
        self.settings.set("capture_backend", self.capture_backend.currentText())
        self.settings.set(
            "capture_region",
            {
                "left": self.region_left.value(),
                "top": self.region_top.value(),
                "width": self.region_width.value(),
                "height": self.region_height.value(),
            },
        )
        self.settings.set("capture_fps", self.capture_fps.currentData())
        self.settings.set("capture_aspect_box_enabled", self.aspect_box_enabled.isChecked())
        self.settings.set("preview_fps", int(self.preview_fps.currentText()))
        self.settings.set("serial_device", self.ser_device.currentText())
        self.settings.set("serial_protocol", self.ser_protocol.currentText())
        self.settings.set("serial_baud", int(self.ser_baud.currentText()))

    def _update_source_field_state(self, source_type: str) -> None:
        is_camera = source_type == "camera"
        is_window = source_type == "window"
        is_region = source_type == "screen_region"
        self.cap_device.setEnabled(is_camera)
        self.window_source.setEnabled(is_window)
        self.window_match_mode.setEnabled(is_window)
        self.capture_backend.setEnabled(is_window or is_region)
        for widget in (
            self.region_left,
            self.region_top,
            self.region_width,
            self.region_height,
        ):
            widget.setEnabled(is_region)

    def _region_spinbox(self, value: object, *, minimum: int = -100000) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, 100000)
        spinbox.setValue(int(value))
        return spinbox


def _source_file(obj: object) -> str:
    try:
        return inspect.getfile(type(obj))
    except TypeError:
        return type(obj).__module__
