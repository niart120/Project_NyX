from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, 
    QLineEdit, QComboBox, QSpinBox, QPushButton, QHBoxLayout, QGroupBox
)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.cap_device.addItems(["Device1", "Device2"])  # プロト用ダミー
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
        self.ser_device.addItems(["COM1", "COM2"])  # プロト用ダミー
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
