from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,  # 追加
    QLineEdit,
    QPushButton,   # 追加
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QHeaderView,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon  # 追加
import os  # 追加


class MacroBrowserPane(QWidget):
    """
    Pane for displaying and filtering available macros, exposes selection change signal.
    """

    selection_changed = Signal(bool)

    def __init__(self, executor, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # --- 検索ボックスとリロードボタンを横並びに配置 ---
        search_reload_layout = QHBoxLayout()
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("検索…（マクロ名／タグ）")
        search_reload_layout.addWidget(self.search_box)

        self.reload_button = QPushButton(self)
        self.reload_button.setToolTip("マクロを再読み込み")
        # アイコンがあれば設定（なければテキスト）
        icon_path = os.path.join(os.path.dirname(__file__), '../../assets/reload.png')
        if os.path.exists(icon_path):
            self.reload_button.setIcon(QIcon(icon_path))
        else:
            self.reload_button.setText("リロード")
        search_reload_layout.addWidget(self.reload_button)
        layout.addLayout(search_reload_layout)
        # --- ここまで ---

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["マクロ名", "説明文", "タグ"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.table)

        self.executor = executor
        self.macros = self.executor.macros
        self.update_macro_table()

        self.search_box.textChanged.connect(self.apply_macro_filter)
        self.reload_button.clicked.connect(self.on_reload_button_clicked)

        self.table.selectionModel().selectionChanged.connect(
            lambda: self.selection_changed.emit(
                self.table.selectionModel().hasSelection()
            )
        )

    def on_reload_button_clicked(self):
        # macrosを再取得し、テーブルを更新
        if hasattr(self.executor, 'reload_macros'):
            self.executor.reload_macros()
            self.macros = self.executor.macros
        else:
            self.macros = self.executor.macros
        self.update_macro_table()

    def update_macro_table(self):
        self.table.setRowCount(0)
        for name, macro in self.macros.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(macro.description))
            self.table.setItem(row, 2, QTableWidgetItem(", ".join(macro.tags)))

    def apply_macro_filter(self):
        keyword = self.search_box.text().lower()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            tags = self.table.item(row, 2).text().split(", ")
            match_keyword = (keyword in name) or any(keyword in t.lower() for t in tags)
            self.table.setRowHidden(row, not (match_keyword))
