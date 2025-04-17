from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, 
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit
)
from nyxpy.gui.settings_dialog import SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Switch Automation Macro GUI - Prototype")
        self.resize(1000, 600)

        # File menu → Settings
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(settings_action)

        # Central layout: Left (macros) / Right (log & preview)
        central = QWidget()
        main_layout = QHBoxLayout(central)
        self.setCentralWidget(central)

        # Left pane
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(5,5,5,5)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("検索…（マクロ名／タグ）")
        self.search_box.textChanged.connect(self.filter_macros)
        left_layout.addWidget(self.search_box)

        # Tags filter
        self.tag_list = QListWidget()
        for tag in ["CategoryA", "CategoryB", "CategoryC"]:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tag_list.addItem(item)
        self.tag_list.itemChanged.connect(self.filter_macros)
        left_layout.addWidget(self.tag_list)

        # Macro table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["マクロ名", "説明文", "タグ"])
        left_layout.addWidget(self.table)

        # Populate example macros
        self.macros = [
            {"name": "Macro1", "desc": "説明1", "tags": ["CategoryA"]},
            {"name": "Macro2", "desc": "説明2", "tags": ["CategoryB"]},
            {"name": "MacroAB", "desc": "説明3", "tags": ["CategoryA","CategoryB"]},
        ]
        self.reload_macros()

        # Right pane: splitter for preview / logs
        right_splitter = QSplitter(Qt.Vertical)
        # Preview placeholder
        self.preview_label = QLabel("プレビュー映像")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #222; color: #fff;")
        right_splitter.addWidget(self.preview_label)

        # Log view
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        right_splitter.addWidget(self.log_view)
        right_splitter.setSizes([300, 300])

        # Assemble split panes
        main_layout.addWidget(left_pane, 3)
        main_layout.addWidget(right_splitter, 5)

        # Timer to simulate real-time logs
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(1000)
        self.log_timer.timeout.connect(self.append_log)
        self.log_timer.start()

        self.log_counter = 0

    def reload_macros(self):
        self.table.setRowCount(0)
        for m in self.macros:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(m["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(m["desc"]))
            self.table.setItem(row, 2, QTableWidgetItem(", ".join(m["tags"])))

    def filter_macros(self):
        keyword = self.search_box.text().lower()
        checked = [self.tag_list.item(i).text() 
                   for i in range(self.tag_list.count()) 
                   if self.tag_list.item(i).checkState() == Qt.Checked]

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            tags = self.table.item(row, 2).text().split(", ")
            # 部分一致 AND 条件
            match_keyword = (keyword in name) or any(keyword in t.lower() for t in tags)
            match_tags = all(tag in tags for tag in checked)
            visible = match_keyword and match_tags
            self.table.setRowHidden(row, not visible)

    def append_log(self):
        self.log_counter += 1
        self.log_view.append(f"[{self.log_counter:03d}] ログメッセージ例: Macro処理中…")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()
