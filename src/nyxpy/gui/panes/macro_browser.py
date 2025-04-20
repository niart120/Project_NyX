from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QSizePolicy, QHeaderView
from PySide6.QtCore import Qt, Signal
from nyxpy.framework.core.utils.helper import extract_macro_tags

class MacroBrowserPane(QWidget):
    """
    Pane for displaying and filtering available macros, exposes selection change signal.
    """
    selection_changed = Signal(bool)

    def __init__(self, executor, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("検索…（マクロ名／タグ）")
        layout.addWidget(self.search_box)

        self.tag_list = QListWidget(self)
        layout.addWidget(self.tag_list)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["マクロ名", "説明文", "タグ"])
        # Allow table columns to be resized interactively and shrink
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.table)

        self.executor = executor
        self.macros = self.executor.macros
        self.reload_macros()
        self.tag_list.clear()
        for tag in extract_macro_tags(self.macros):
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tag_list.addItem(item)

        # connect filter and selection within pane
        self.search_box.textChanged.connect(self.filter_macros)
        self.tag_list.itemChanged.connect(self.filter_macros)
        # emit selection changes
        self.table.selectionModel().selectionChanged.connect(
            lambda: self.selection_changed.emit(self.table.selectionModel().hasSelection())
        )

    def reload_macros(self):
        self.table.setRowCount(0)
        for name, macro in self.macros.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(macro.description))
            self.table.setItem(row, 2, QTableWidgetItem(", ".join(macro.tags)))

    def filter_macros(self):
        keyword = self.search_box.text().lower()
        checked = [self.tag_list.item(i).text() 
                   for i in range(self.tag_list.count()) 
                   if self.tag_list.item(i).checkState() == Qt.Checked]

        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            tags = self.table.item(row, 2).text().split(", ")
            match_keyword = (keyword in name) or any(keyword in t.lower() for t in tags)
            match_tags = all(tag in tags for tag in checked)
            self.table.setRowHidden(row, not (match_keyword and match_tags))
