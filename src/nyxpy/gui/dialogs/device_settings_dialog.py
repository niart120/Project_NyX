from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QDialogButtonBox, QMessageBox
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager

class DeviceSettingsDialog(QDialog):
    def __init__(self, parent=None, settings: GlobalSettings=None, capture_manager=None, serial_manager=None):
        super().__init__(parent)
        self.settings = settings or GlobalSettings()
        self.setWindowTitle("デバイス設定")
        self.resize(400, 200)
        
        # 既存のマネージャを使用するか、新しく作成する
        self.capture_manager = capture_manager or CaptureManager()
        self.serial_manager = serial_manager or SerialManager()

        layout = QVBoxLayout(self)

        # キャプチャデバイス設定
        cap_form = QFormLayout()
        self.cap_device = QComboBox()
        # 既存のキャプチャマネージャを使用
        self.capture_manager.auto_register_devices()
        devices = self.capture_manager.list_devices()
        self.cap_device.addItems(devices)
        current_cap = self.settings.get("capture_device", "")
        if current_cap in devices:
            self.cap_device.setCurrentText(current_cap)
        self.cap_fps = QComboBox()
        # FPS options: 15, 30, 60
        fps_options = ["15", "30", "60"]
        self.cap_fps.addItems(fps_options)
        # Set current FPS
        current_fps = str(self.settings.get("capture_fps", 30))
        if current_fps in fps_options:
            self.cap_fps.setCurrentText(current_fps)
        else:
            self.cap_fps.setCurrentText("30")
        cap_form.addRow("デバイス:", self.cap_device)
        cap_form.addRow("FPS:", self.cap_fps)
        layout.addLayout(cap_form)

        # シリアルデバイス設定
        ser_form = QFormLayout()
        self.ser_device = QComboBox()
        # 既存のシリアルマネージャを使用
        self.serial_manager.auto_register_devices()
        serials = self.serial_manager.list_devices()
        self.ser_device.addItems(serials)
        current_ser = self.settings.get("serial_device", "")
        if current_ser in serials:
            self.ser_device.setCurrentText(current_ser)
        self.ser_baud = QComboBox()
        # Common serial baud rates
        baud_options = ["1200", "2400", "4800", "9600", "14400", "19200", "38400", "57600", "115200"]
        self.ser_baud.addItems(baud_options)
        # Set current baud rate
        current_baud = str(self.settings.get("serial_baud", 9600))
        if current_baud in baud_options:
            self.ser_baud.setCurrentText(current_baud)
        else:
            self.ser_baud.setCurrentText("9600")
        ser_form.addRow("デバイス:", self.ser_device)
        ser_form.addRow("ボーレート:", self.ser_baud)
        layout.addLayout(ser_form)

        # デバイスが見つからない場合の警告
        if not devices and not serials:
            QMessageBox.warning(
                self,
                "デバイス検出エラー",
                "キャプチャデバイスとシリアルデバイスが見つかりませんでした。\n"
                "デバイスが接続されていることを確認してください。"
            )
        elif not serials:
            QMessageBox.warning(
                self,
                "デバイス検出エラー",
                "シリアルデバイスが見つかりませんでした。\n"
                "シリアルデバイスが接続されていることを確認してください。"
            )

        # ボタン
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.settings.set("capture_device", self.cap_device.currentText())
        # Set selected FPS from dropdown
        self.settings.set("capture_fps", int(self.cap_fps.currentText()))
        self.settings.set("serial_device", self.ser_device.currentText())
        # Set selected baud rate from dropdown
        self.settings.set("serial_baud", int(self.ser_baud.currentText()))
        super().accept()
