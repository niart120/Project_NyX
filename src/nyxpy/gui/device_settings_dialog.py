from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QSpinBox, QDialogButtonBox
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager

class DeviceSettingsDialog(QDialog):
    def __init__(self, parent=None, settings: GlobalSettings=None):
        super().__init__(parent)
        self.settings = settings or GlobalSettings()
        self.setWindowTitle("デバイス設定")
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        # Capture device settings
        cap_form = QFormLayout()
        self.cap_device = QComboBox()
        cap_mgr = CaptureManager()
        cap_mgr.auto_register_devices()
        devices = cap_mgr.list_devices()
        self.cap_device.addItems(devices)
        current_cap = self.settings.get("capture_device", "")
        if current_cap in devices:
            self.cap_device.setCurrentText(current_cap)
        self.cap_fps = QSpinBox()
        self.cap_fps.setRange(1, 60)
        self.cap_fps.setValue(self.settings.get("capture_fps", 30))
        cap_form.addRow("デバイス:", self.cap_device)
        cap_form.addRow("FPS:", self.cap_fps)
        layout.addLayout(cap_form)

        # Serial device settings
        ser_form = QFormLayout()
        self.ser_device = QComboBox()
        ser_mgr = SerialManager()
        ser_mgr.auto_register_devices()
        serials = ser_mgr.list_devices()
        self.ser_device.addItems(serials)
        current_ser = self.settings.get("serial_device", "")
        if current_ser in serials:
            self.ser_device.setCurrentText(current_ser)
        self.ser_baud = QSpinBox()
        self.ser_baud.setRange(1200, 115200)
        self.ser_baud.setValue(self.settings.get("serial_baud", 9600))
        ser_form.addRow("デバイス:", self.ser_device)
        ser_form.addRow("ボーレート:", self.ser_baud)
        layout.addLayout(ser_form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.settings.set("capture_device", self.cap_device.currentText())
        self.settings.set("capture_fps", self.cap_fps.value())
        self.settings.set("serial_device", self.ser_device.currentText())
        self.settings.set("serial_baud", self.ser_baud.value())
        super().accept()