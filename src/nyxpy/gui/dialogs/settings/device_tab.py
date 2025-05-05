from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QComboBox, QPushButton, QGroupBox, QLabel, QHBoxLayout
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.secrets_settings import SecretsSettings
from nyxpy.framework.core.singletons import serial_manager, capture_manager
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory

class DeviceSettingsTab(QWidget):
    def __init__(self, settings:GlobalSettings, secrets:SecretsSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.secrets = secrets
        layout = QFormLayout(self)

        # キャプチャ関連設定
        cap_group = QGroupBox("キャプチャデバイス")
        cap_group_layout = QVBoxLayout(cap_group)
        cap_form = QFormLayout()

        # キャプチャデバイス一覧
        cap_row = QHBoxLayout()
        self.cap_device = QComboBox()
        self.refresh_capture_devices()
        refresh_btn = QPushButton("リロード")
        refresh_btn.setFixedWidth(60)
        refresh_btn.clicked.connect(self.refresh_capture_devices)
        cap_row.addWidget(self.cap_device)
        cap_row.addWidget(refresh_btn)
        cap_form.addRow(QLabel("Device:"), cap_row)
        
        # プレビューFPS
        fps_options = ["15", "30", "60"]
        self.preview_fps = QComboBox()
        self.preview_fps.addItems(fps_options)
        current_preview_fps = str(self.settings.get("preview_fps", 60))
        if current_preview_fps in fps_options:
            self.preview_fps.setCurrentText(current_preview_fps)
        cap_form.addRow(QLabel("Preview FPS:"), self.preview_fps)
        cap_group_layout.addLayout(cap_form)
        layout.addWidget(cap_group)

        # シリアルデバイス設定
        ser_group = QGroupBox("シリアルデバイス")
        ser_group_layout = QVBoxLayout(ser_group)
        ser_form = QFormLayout()

        # シリアルデバイス一覧
        ser_row = QHBoxLayout()
        self.ser_device = QComboBox()
        self.refresh_serial_devices()
        refresh_ser_btn = QPushButton("リロード")
        refresh_ser_btn.setFixedWidth(60)
        refresh_ser_btn.clicked.connect(self.refresh_serial_devices)
        ser_row.addWidget(self.ser_device)
        ser_row.addWidget(refresh_ser_btn)
        ser_form.addRow(QLabel("Device:"), ser_row)

        # シリアルプロトコル
        self.ser_protocol = QComboBox()
        protocol_options = ProtocolFactory.get_protocol_names()
        self.ser_protocol.addItems(protocol_options)
        current_protocol = self.settings.get("serial_protocol", "")
        if current_protocol in protocol_options:
            self.ser_protocol.setCurrentText(current_protocol)

        # シリアルボーレート
        self.ser_baud = QComboBox()
        baud_options = [
            "1200", "2400", "4800", "9600", "14400", "19200", "38400", "57600", "115200",
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

    def refresh_capture_devices(self):
        devices = capture_manager.list_devices()
        self.cap_device.clear()
        self.cap_device.addItems(devices)
        current_cap = self.settings.get("capture_device", "")
        if current_cap in devices:
            self.cap_device.setCurrentText(current_cap)

    def refresh_serial_devices(self):
        serials = serial_manager.list_devices()
        self.ser_device.clear()
        self.ser_device.addItems(serials)
        current_ser = self.settings.get("serial_device", "")
        if current_ser in serials:
            self.ser_device.setCurrentText(current_ser)

    def apply(self):
        self.settings.set("capture_device", self.cap_device.currentText())
        self.settings.set("preview_fps", int(self.preview_fps.currentText()))
        self.settings.set("serial_device", self.ser_device.currentText())
        self.settings.set("serial_protocol", self.ser_protocol.currentText())
        self.settings.set("serial_baud", int(self.ser_baud.currentText()))
