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


def macro_leaf_labels(widget: MacroBrowserPane) -> list[str]:
    labels: list[str] = []
    for index in range(widget.explorer_tree.topLevelItemCount()):
        collect_macro_leaf_labels(widget.explorer_tree.topLevelItem(index), labels)
    return labels


def collect_macro_leaf_labels(item, labels: list[str]) -> None:
    if item.data(0, Qt.ItemDataRole.UserRole):
        labels.append(item.text(0))
    for index in range(item.childCount()):
        collect_macro_leaf_labels(item.child(index), labels)


def test_macro_reload_add_and_remove(
    qtbot, macro_browser: MacroBrowserPane, macros_dir: Path
) -> None:
    initial_count = len(macro_leaf_labels(macro_browser))
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

    labels = macro_leaf_labels(macro_browser)
    assert len(labels) == initial_count + 1
    assert "DummyMacro" in labels

    new_macro_path.unlink()
    qtbot.mouseClick(macro_browser.reload_button, Qt.LeftButton)

    assert len(macro_leaf_labels(macro_browser)) == initial_count
