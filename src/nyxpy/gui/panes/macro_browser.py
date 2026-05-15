from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nyxpy.gui.layout import LEFT_PANE_CONTENT_MARGIN
from nyxpy.gui.typography import apply_pane_title_font


class MacroBrowserPane(QWidget):
    """
    Pane for displaying and filtering available macros, exposes selection change signal.
    """

    selection_changed = Signal(bool)

    def __init__(self, catalog, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
        )
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("マクロ", self)
        apply_pane_title_font(self.title_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        self.reload_button = QPushButton(self)
        self.reload_button.setToolTip("マクロを再読み込み")
        self.reload_button.setText("リロード")
        header_layout.addWidget(self.reload_button)
        layout.addLayout(header_layout)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["マクロ名", "タグ"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self.catalog = catalog
        self.update_macro_table()

        self.reload_button.clicked.connect(self.on_reload_button_clicked)

        self.table.selectionModel().selectionChanged.connect(
            lambda: self.selection_changed.emit(self.table.selectionModel().hasSelection())
        )

    def on_reload_button_clicked(self):
        self.catalog.reload_macros()
        self.update_macro_table()

    def update_macro_table(self):
        self.table.setRowCount(0)
        for macro in self.catalog.list():
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(macro.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, macro.id)
            name_item.setToolTip(macro.class_name)
            self.table.setItem(row, 0, name_item)
            name_item.setToolTip(macro.description or macro.class_name)
            self.table.setItem(row, 1, QTableWidgetItem(", ".join(macro.tags)))

    def selected_macro_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        macro_id = item.data(Qt.ItemDataRole.UserRole)
        return str(macro_id) if macro_id else None

    def selected_macro_display_name(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item is not None else None
