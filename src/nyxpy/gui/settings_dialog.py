from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, 
    QLineEdit, QComboBox, QSpinBox, QPushButton, QHBoxLayout, QGroupBox
)
from pathlib import Path
import tomllib
from nyxpy.framework.core.hardware.capture import CaptureManager
from nyxpy.framework.core.hardware.serial_comm import SerialManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None, macro_name: str = None):
        super().__init__(parent)
        self.macro_name = macro_name
        self.setWindowTitle("実行設定")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Execution parameters
        param_group = QGroupBox("実行パラメータ")
        param_layout = QVBoxLayout(param_group)
        self.param_edit = QLineEdit()
        self.param_edit.setPlaceholderText("例: key1=val1 key2=val2 ...")
        param_layout.addWidget(self.param_edit)
        layout.addWidget(param_group)

        # Capture device settings
        cap_group = QGroupBox("キャプチャデバイス設定")
        cap_form = QFormLayout(cap_group)
        self.cap_device = QComboBox()
        # Populate capture devices
        cap_mgr = CaptureManager()
        cap_mgr.auto_register_devices()
        self.cap_device.addItems(cap_mgr.list_devices())
        self.cap_fps = QSpinBox()
        self.cap_fps.setRange(1, 60)
        self.cap_fps.setValue(30)
        cap_form.addRow("デバイス:", self.cap_device)
        cap_form.addRow("FPS:", self.cap_fps)
        layout.addWidget(cap_group)

        # Serial device settings
        ser_group = QGroupBox("シリアルデバイス設定")
        ser_form = QFormLayout(ser_group)
        self.ser_device = QComboBox()
        # Populate serial devices
        ser_mgr = SerialManager()
        ser_mgr.auto_register_devices()
        self.ser_device.addItems(ser_mgr.list_devices())
        self.ser_baud = QSpinBox()
        self.ser_baud.setRange(1200, 115200)
        self.ser_baud.setValue(9600)
        ser_form.addRow("デバイス:", self.ser_device)
        ser_form.addRow("ボーレート:", self.ser_baud)
        layout.addWidget(ser_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Load persisted settings if available
        if self.macro_name:
            settings_file = Path.cwd() / "static" / self.macro_name / "settings.toml"
            if settings_file.exists():
                params = tomllib.loads(settings_file.read_text())
                self.param_edit.setText(params.get("param_edit", ""))
                self.cap_device.setCurrentText(str(params.get("cap_device", self.cap_device.currentText())))
                self.cap_fps.setValue(int(params.get("cap_fps", self.cap_fps.value())))
                self.ser_device.setCurrentText(str(params.get("ser_device", self.ser_device.currentText())))
                self.ser_baud.setValue(int(params.get("ser_baud", self.ser_baud.value())))

    def accept(self) -> None:
        # Persist settings to static/<macro_name>/settings.toml
        if self.macro_name:
            settings_dir = Path.cwd() / "static" / self.macro_name
            settings_dir.mkdir(parents=True, exist_ok=True)
            settings_file = settings_dir / "settings.toml"
            content = []
            content.append(f'param_edit = "{self.param_edit.text()}"')
            content.append(f'cap_device = "{self.cap_device.currentText()}"')
            content.append(f'cap_fps = {self.cap_fps.value()}')
            content.append(f'ser_device = "{self.ser_device.currentText()}"')
            content.append(f'ser_baud = {self.ser_baud.value()}')
            settings_file.write_text("\n".join(content))
        super().accept()
