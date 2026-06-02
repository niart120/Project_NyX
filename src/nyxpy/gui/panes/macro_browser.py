"""マクロ一覧 pane。"""

from typing import Literal

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nyxpy.gui.layout import LEFT_PANE_CONTENT_MARGIN
from nyxpy.gui.macro_explorer_model import (
    MacroExplorerNode,
    build_explorer_tree,
    search_macros,
)
from nyxpy.gui.typography import apply_pane_title_font

ViewMode = Literal["explorer", "search"]


class MacroBrowserPane(QWidget):
    """Pane for displaying and filtering available macros, exposes selection change signal."""

    selection_changed = Signal(bool)

    def __init__(self, catalog, parent=None):
        """Macro catalog を保持し、Explorer / Search view を作成します。"""
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
            LEFT_PANE_CONTENT_MARGIN,
        )
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("マクロ", self)
        apply_pane_title_font(self.title_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        self.view_button_group = QButtonGroup(self)
        self.view_button_group.setExclusive(True)
        self.explorer_button = QToolButton(self)
        self.explorer_button.setText("Explorer")
        self.explorer_button.setCheckable(True)
        self.search_button = QToolButton(self)
        self.search_button.setText("Search")
        self.search_button.setCheckable(True)
        self.view_button_group.addButton(self.explorer_button)
        self.view_button_group.addButton(self.search_button)
        header_layout.addWidget(self.explorer_button)
        header_layout.addWidget(self.search_button)
        self.reload_button = QPushButton(self)
        self.reload_button.setToolTip("マクロを再読み込み")
        self.reload_button.setText("リロード")
        header_layout.addWidget(self.reload_button)
        layout.addLayout(header_layout)

        self.stack = QStackedWidget(self)
        self.explorer_tree = QTreeWidget(self.stack)
        self.explorer_tree.setHeaderHidden(True)
        self.explorer_tree.setRootIsDecorated(True)
        self.stack.addWidget(self.explorer_tree)

        self.search_page = QWidget(self.stack)
        search_layout = QVBoxLayout(self.search_page)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit(self.search_page)
        self.search_input.setPlaceholderText("Search")
        self.search_results = QListWidget(self.search_page)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_results, 1)
        self.stack.addWidget(self.search_page)
        layout.addWidget(self.stack, 1)

        self.catalog = catalog
        self._view_mode: ViewMode = "explorer"
        self._query = ""
        self._selected_macro_id: str | None = None
        self._updating_selection = False
        self.update_macro_view()
        self.set_view_mode("explorer")

        self.reload_button.clicked.connect(self.on_reload_button_clicked)
        self.explorer_button.clicked.connect(lambda: self.set_view_mode("explorer"))
        self.search_button.clicked.connect(lambda: self.set_view_mode("search"))
        self.search_input.textChanged.connect(self.set_search_query)
        self.explorer_tree.itemSelectionChanged.connect(self._on_explorer_selection_changed)
        self.search_results.itemSelectionChanged.connect(self._on_search_selection_changed)
        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.search_shortcut.activated.connect(self._focus_search)
        self.search_input.installEventFilter(self)

    def on_reload_button_clicked(self):
        selected_macro_id = self._selected_macro_id
        view_mode = self._view_mode
        query = self._query
        self.catalog.reload_macros()
        self._query = query
        self.update_macro_view()
        self.set_view_mode(view_mode)
        if selected_macro_id and self._definition_exists(selected_macro_id):
            self._set_selected_macro_id(selected_macro_id, emit=False)
            self._restore_selection()
            return
        self._set_selected_macro_id(None)

    def update_macro_view(self):
        self._rebuild_explorer_tree()
        self._rebuild_search_results()
        if self._selected_macro_id and not self._definition_exists(self._selected_macro_id):
            self._set_selected_macro_id(None)
        else:
            self._restore_selection()

    def set_view_mode(self, mode: ViewMode) -> None:
        self._view_mode = mode
        self.explorer_button.setChecked(mode == "explorer")
        self.search_button.setChecked(mode == "search")
        self.stack.setCurrentWidget(self.search_page if mode == "search" else self.explorer_tree)
        self._restore_selection()
        if mode == "search":
            if self._selected_macro_id and not self._search_contains(self._selected_macro_id):
                self._set_selected_macro_id(None)
            self.search_input.setFocus()

    def set_search_query(self, query: str) -> None:
        self._query = query
        if self.search_input.text() != query:
            blocked = self.search_input.blockSignals(True)
            try:
                self.search_input.setText(query)
            finally:
                self.search_input.blockSignals(blocked)
        self._rebuild_search_results()
        if self._view_mode == "search":
            if self._selected_macro_id and not self._search_contains(self._selected_macro_id):
                self._set_selected_macro_id(None)
            else:
                self._restore_selection()

    def eventFilter(self, watched, event):
        if (
            watched is self.search_input
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            if self.search_input.text():
                self.search_input.clear()
            else:
                self.set_view_mode("explorer")
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Find):
            self._focus_search()
            event.accept()
            return
        super().keyPressEvent(event)

    def selected_macro_id(self) -> str | None:
        return self._selected_macro_id

    def selected_macro_display_name(self) -> str | None:
        if self._selected_macro_id is None:
            return None
        try:
            return self.catalog.get(self._selected_macro_id).display_name
        except (KeyError, StopIteration):
            return None

    def _focus_search(self) -> None:
        self.set_view_mode("search")
        self.search_input.setFocus()

    def _rebuild_explorer_tree(self) -> None:
        self._updating_selection = True
        try:
            self.explorer_tree.clear()
            roots = self._search_roots()
            for node in build_explorer_tree(tuple(self.catalog.list()), roots):
                self.explorer_tree.addTopLevelItem(self._tree_item(node))
            self.explorer_tree.expandAll()
        finally:
            self._updating_selection = False

    def _rebuild_search_results(self) -> None:
        self._updating_selection = True
        try:
            self.search_results.clear()
            for result in search_macros(tuple(self.catalog.list()), self._query):
                definition = self.catalog.get(result.macro_id)
                item = QListWidgetItem(result.display_name)
                item.setData(Qt.ItemDataRole.UserRole, result.macro_id)
                item.setToolTip(self._tooltip_for_definition(definition))
                self.search_results.addItem(item)
        finally:
            self._updating_selection = False

    def _tree_item(self, node: MacroExplorerNode) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.label])
        item.setData(0, Qt.ItemDataRole.UserRole, node.macro_id)
        if node.macro_id:
            item.setToolTip(0, self._tooltip_for_definition(self.catalog.get(node.macro_id)))
        for child in node.children:
            item.addChild(self._tree_item(child))
        return item

    def _tooltip_for_definition(self, definition) -> str:
        lines = [
            str(definition.display_name),
            f"ID: {definition.id}",
            f"Class: {definition.class_name}",
        ]
        if definition.tags:
            lines.append(f"Tags: {', '.join(definition.tags)}")
        if definition.description:
            lines.append(str(definition.description))
        return "\n".join(lines)

    def _on_explorer_selection_changed(self) -> None:
        if self._updating_selection:
            return
        item = self.explorer_tree.currentItem()
        macro_id = self._macro_id_from_tree_item(item)
        self._set_selected_macro_id(macro_id)

    def _on_search_selection_changed(self) -> None:
        if self._updating_selection:
            return
        item = self.search_results.currentItem()
        macro_id = self._macro_id_from_list_item(item)
        self._set_selected_macro_id(macro_id)

    def _set_selected_macro_id(self, macro_id: str | None, *, emit: bool = True) -> None:
        self._selected_macro_id = macro_id if macro_id and self._definition_exists(macro_id) else None
        self._restore_selection()
        if emit:
            self.selection_changed.emit(self._selected_macro_id is not None)

    def _restore_selection(self) -> None:
        self._updating_selection = True
        try:
            self._select_tree_macro_id(self._selected_macro_id)
            self._select_search_macro_id(self._selected_macro_id)
        finally:
            self._updating_selection = False

    def _select_tree_macro_id(self, macro_id: str | None) -> None:
        self.explorer_tree.clearSelection()
        if macro_id is None:
            return
        item = self._find_tree_item(macro_id)
        if item is not None:
            self.explorer_tree.setCurrentItem(item)

    def _select_search_macro_id(self, macro_id: str | None) -> None:
        self.search_results.clearSelection()
        if macro_id is None:
            return
        for row in range(self.search_results.count()):
            item = self.search_results.item(row)
            if self._macro_id_from_list_item(item) == macro_id:
                self.search_results.setCurrentItem(item)
                return

    def _find_tree_item(self, macro_id: str) -> QTreeWidgetItem | None:
        for index in range(self.explorer_tree.topLevelItemCount()):
            item = self.explorer_tree.topLevelItem(index)
            if item is None:
                continue
            found = self._find_tree_item_recursive(item, macro_id)
            if found is not None:
                return found
        return None

    def _find_tree_item_recursive(
        self,
        item: QTreeWidgetItem,
        macro_id: str,
    ) -> QTreeWidgetItem | None:
        if self._macro_id_from_tree_item(item) == macro_id:
            return item
        for index in range(item.childCount()):
            found = self._find_tree_item_recursive(item.child(index), macro_id)
            if found is not None:
                return found
        return None

    def _macro_id_from_tree_item(self, item: QTreeWidgetItem | None) -> str | None:
        if item is None:
            return None
        macro_id = item.data(0, Qt.ItemDataRole.UserRole)
        return str(macro_id) if macro_id and self._definition_exists(str(macro_id)) else None

    def _macro_id_from_list_item(self, item: QListWidgetItem | None) -> str | None:
        if item is None:
            return None
        macro_id = item.data(Qt.ItemDataRole.UserRole)
        return str(macro_id) if macro_id and self._definition_exists(str(macro_id)) else None

    def _definition_exists(self, macro_id: str) -> bool:
        try:
            self.catalog.get(macro_id)
        except (KeyError, StopIteration):
            return False
        return True

    def _search_contains(self, macro_id: str) -> bool:
        for row in range(self.search_results.count()):
            if self._macro_id_from_list_item(self.search_results.item(row)) == macro_id:
                return True
        return False

    def _search_roots(self):
        search_roots = getattr(self.catalog, "search_roots", None)
        if callable(search_roots):
            return tuple(search_roots())
        return ()
