from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.gui.macro_catalog import MacroCatalog
from nyxpy.gui.panes.macro_browser import MacroBrowserPane


@pytest.fixture
def macros_dir(tmp_path: Path) -> Path:
    path = tmp_path / "macros"
    path.mkdir()
    return path


@pytest.fixture
def macro_catalog(tmp_path: Path, macros_dir: Path) -> MacroCatalog:
    return MacroCatalog(MacroRegistry(project_root=tmp_path))


@pytest.fixture
def macro_browser(qtbot, macro_catalog: MacroCatalog) -> MacroBrowserPane:
    widget = MacroBrowserPane(macro_catalog)
    qtbot.addWidget(widget)
    return widget


def test_macro_reload_add_and_remove(
    qtbot, macro_browser: MacroBrowserPane, macros_dir: Path
) -> None:
    initial_count = macro_browser.table.rowCount()
    new_macro_path = macros_dir / "dummy_macro.py"

    new_macro_path.write_text(
        """\
from nyxpy.framework.core.macro.base import MacroBase


class DummyMacro(MacroBase):
    description = "dummy"
    tags = ["test"]

    def initialize(self, cmd, args): pass
    def run(self, cmd): pass
    def finalize(self, cmd): pass
""",
        encoding="utf-8",
    )
    qtbot.mouseClick(macro_browser.reload_button, Qt.LeftButton)

    assert macro_browser.table.rowCount() == initial_count + 1
    assert any(
        "DummyMacro" in macro_browser.table.item(row, 0).text()
        for row in range(macro_browser.table.rowCount())
    )

    new_macro_path.unlink()
    qtbot.mouseClick(macro_browser.reload_button, Qt.LeftButton)

    assert macro_browser.table.rowCount() == initial_count
