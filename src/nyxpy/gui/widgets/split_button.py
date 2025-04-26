from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QToolButton, QMenu, QSizePolicy, QProxyStyle, QStyle, QStyleOptionButton
from PySide6.QtCore import Qt, Signal

class CustomSplitDropDownButton(QWidget):
    """
    A button with a main action and a dropdown menu for additional actions.
    Used for macro execution with optional parameter input.
    """
    # Main button clicked signal
    main_clicked = Signal()

    def __init__(self, main_text="Action", dropdown_items=None, parent=None):
        super().__init__(parent)
        self.main_text = main_text
        # dropdown_items format: [(action_text, callable), ...]
        self.dropdown_items = dropdown_items if dropdown_items is not None else []
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()

    def _create_widgets(self):
        self.mainButton = QPushButton(self.main_text, self)
        self.mainButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        #self.mainButton.setStyleSheet("margin-right: 0px; ")

        self.dropdownButton = QToolButton(self)
        self.dropdownButton.setArrowType(Qt.DownArrow)
        self.dropdownButton.setPopupMode(QToolButton.InstantPopup)
        self.dropdownButton.setFocusPolicy(Qt.NoFocus)
        self.dropdownButton.setStyleSheet("margin-left: -1px; ")

        self.dropdownMenu = QMenu(self)
        self._populate_menu()
        self.dropdownButton.setMenu(self.dropdownMenu)

    def _setup_layout(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # ボタン間のスペースを0に設定
        layout.addWidget(self.mainButton)
        layout.addWidget(self.dropdownButton)
        self.setLayout(layout)

    def _connect_signals(self):
        self.mainButton.clicked.connect(self.main_clicked.emit)

    def _populate_menu(self):
        """Add items to the dropdown menu"""
        self.dropdownMenu.clear()
        for item in self.dropdown_items:
            if isinstance(item, tuple) and len(item) >= 2:
                action_text, callback = item[:2]
                self.dropdownMenu.addAction(action_text, callback)
            else:
                # Add text-only item if no callback provided
                self.dropdownMenu.addAction(str(item))

    def set_dropdown_items(self, items):
        """Update dropdown menu items"""
        self.dropdown_items = items
        self._populate_menu()

    def set_main_text(self, text):
        """Update main button text"""
        self.main_text = text
        self.mainButton.setText(text)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.mainButton.setEnabled(enabled)
        self.dropdownButton.setEnabled(enabled)
        self.dropdownButton.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)

    def isEnabled(self):
        """Return enabled state of the button"""
        return self.mainButton.isEnabled()
