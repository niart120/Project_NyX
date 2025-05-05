from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QGroupBox,
)


class MacroParamsDialog(QDialog):
    def __init__(self, parent=None, macro_name: str = None):
        super().__init__(parent)
        # Execution parameter dialog for macro run
        self.setWindowTitle("実行パラメータ")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Execution parameters
        param_group = QGroupBox("実行パラメータ")
        param_layout = QVBoxLayout(param_group)
        self.param_edit = QLineEdit()
        self.param_edit.setPlaceholderText("例: key1=val1 key2=val2 ...")
        param_layout.addWidget(self.param_edit)
        layout.addWidget(param_group)

        # Buttons: execute only parameters
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        run_btn = QPushButton("実行")
        run_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
