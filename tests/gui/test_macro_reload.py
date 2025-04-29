import os
import pytest
from PySide6.QtCore import Qt
from nyxpy.gui.panes.macro_browser import MacroBrowserPane
from nyxpy.framework.core.macro.executor import MacroExecutor

@pytest.fixture
def macro_executor():
    return MacroExecutor()

@pytest.fixture
def macro_browser(qtbot, macro_executor):
    widget = MacroBrowserPane(macro_executor)
    qtbot.addWidget(widget)
    return widget

def test_macro_reload_add_and_remove_real_env(qtbot, macro_browser):
    macros_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../macros'))
    initial_count = macro_browser.table.rowCount()

    new_macro_path = os.path.join(macros_dir, 'dummy_macro.py')
    try:
        with open(new_macro_path, 'w', encoding='utf-8') as f:
            f.write('''\
from nyxpy.framework.core.macro.base import MacroBase
class DummyMacro(MacroBase):
    description = "dummy"
    tags = ["test"]
    def initialize(self, cmd, args): pass
    def run(self, cmd): pass
    def finalize(self, cmd): pass
''')
        qtbot.mouseClick(macro_browser.reload_button, Qt.LeftButton)
        qtbot.wait(300)
        assert macro_browser.table.rowCount() == initial_count + 1
        assert any('DummyMacro' in macro_browser.table.item(row, 0).text() for row in range(macro_browser.table.rowCount()))

        os.remove(new_macro_path)
        qtbot.mouseClick(macro_browser.reload_button, Qt.LeftButton)
        qtbot.wait(300)
        assert macro_browser.table.rowCount() == initial_count
    finally:
        if os.path.exists(new_macro_path):
            os.remove(new_macro_path)
