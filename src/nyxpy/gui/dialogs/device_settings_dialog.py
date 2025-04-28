from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
)
from nyxpy.framework.core.global_settings import GlobalSettings
from nyxpy.framework.core.hardware.protocol_factory import ProtocolFactory
from nyxpy.gui.models.device_model import DeviceModel


class DeviceSettingsDialog(QDialog):
    def __init__(
        self,
        parent,
        device_model: DeviceModel,
        settings: GlobalSettings,
    ):
        super().__init__(parent)
        self.device_model = device_model
        self.settings = settings
        self.setWindowTitle("デバイス設定")
        self.resize(400, 250)
        layout = QVBoxLayout(self)

        # キャプチャデバイス設定
        cap_form = QFormLayout()
        self.cap_device = QComboBox()
        devices = self.device_model.get_capture_device_list()
        self.cap_device.addItems(devices)
        current_cap = self.settings.get("capture_device", "")
        if current_cap in devices:
            self.cap_device.setCurrentText(current_cap)
        self.cap_fps = QComboBox()
        fps_options = ["15", "30", "60"]
        self.cap_fps.addItems(fps_options)
        current_fps = str(self.settings.get("capture_fps", 30))
        if current_fps in fps_options:
            self.cap_fps.setCurrentText(current_fps)
        else:
            self.cap_fps.setCurrentText("30")
        # プレビューFPS欄を追加
        self.preview_fps = QComboBox()
        self.preview_fps.addItems(fps_options)
        current_preview_fps = str(self.settings.get("preview_fps", 30))
        if current_preview_fps in fps_options:
            self.preview_fps.setCurrentText(current_preview_fps)
        else:
            self.preview_fps.setCurrentText("30")
        cap_form.addRow("Device:", self.cap_device)
        cap_form.addRow("Device FPS:", self.cap_fps)
        cap_form.addRow("Preview FPS:", self.preview_fps)
        layout.addLayout(cap_form)

        # シリアルデバイス設定
        ser_form = QFormLayout()
        self.ser_device = QComboBox()
        serials = self.device_model.get_serial_device_list()
        self.ser_device.addItems(serials)
        current_ser = self.settings.get("serial_device", "")
        if current_ser in serials:
            self.ser_device.setCurrentText(current_ser)
        self.ser_protocol = QComboBox()
        protocol_options = ProtocolFactory.get_protocol_names()
        self.ser_protocol.addItems(protocol_options)
        current_protocol = self.settings.get("serial_protocol", "CH552")
        if current_protocol in protocol_options:
            self.ser_protocol.setCurrentText(current_protocol)
        else:
            self.ser_protocol.setCurrentText("CH552")
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
        ser_form.addRow("Device:", self.ser_device)
        ser_form.addRow("Protocol:", self.ser_protocol)
        ser_form.addRow("Baud Rate:", self.ser_baud)
        layout.addLayout(ser_form)

        # デバイスが見つからない場合の警告
        if not devices and not serials:
            QMessageBox.warning(
                self,
                "デバイス検出エラー",
                "キャプチャデバイスとシリアルデバイスが見つかりませんでした。\n"
                "デバイスが接続されていることを確認してください。",
            )
        elif not serials:
            QMessageBox.warning(
                self,
                "デバイス検出エラー",
                "シリアルデバイスが見つかりませんでした。\n"
                "シリアルデバイスが接続されていることを確認してください。",
            )

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        # 設定値の保存のみ担当（システム状態の変更は行わない）
        self.settings.set("capture_device", self.cap_device.currentText())
        self.settings.set("capture_fps", int(self.cap_fps.currentText()))
        self.settings.set("serial_device", self.ser_device.currentText())
        self.settings.set("serial_protocol", self.ser_protocol.currentText())
        self.settings.set("serial_baud", int(self.ser_baud.currentText()))
        self.settings.set("preview_fps", int(self.preview_fps.currentText()))
        super().accept()
