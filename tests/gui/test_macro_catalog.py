from __future__ import annotations

from pathlib import Path

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.registry import (
    ClassMacroFactory,
    MacroDefinition,
    MacroSearchRoot,
)
from nyxpy.gui.macro_catalog import MacroCatalog
from nyxpy.gui.panes.macro_browser import MacroBrowserPane


class DummyMacro(MacroBase):
    def run(self, cmd):
        pass


def definition(macro_id: str, *, display_name: str, class_name: str) -> MacroDefinition:
    return MacroDefinition(
        id=macro_id,
        aliases=(class_name,),
        display_name=display_name,
        class_name=class_name,
        module_name="tests.gui.test_macro_catalog",
        macro_root=Path("."),
        source_path=Path(__file__),
        settings_path=None,
        description="desc",
        tags=("tag",),
        factory=ClassMacroFactory(DummyMacro),
    )


class FakeRegistry:
    def __init__(self) -> None:
        self.project_root = Path(".")
        self.macro_search_roots = (
            MacroSearchRoot(Path("macros"), Path("resources")),
            MacroSearchRoot(Path("examples") / "macros", Path("examples") / "resources"),
        )
        self.definitions = [
            definition("macro-b", display_name="B Macro", class_name="SameName"),
            definition("macro-a", display_name="A Macro", class_name="SameName"),
        ]
        self.reloads = 0

    def reload(self) -> None:
        self.reloads += 1

    def list(self):
        return tuple(self.definitions)


def test_macro_catalog_keys_by_definition_id():
    catalog = MacroCatalog(FakeRegistry())  # type: ignore[arg-type]

    assert set(catalog.definitions_by_id) == {"macro-a", "macro-b"}
    assert catalog.get("macro-a").display_name == "A Macro"
    assert not hasattr(catalog, "macros")


def test_macro_catalog_reload_preserves_stable_ids():
    registry = FakeRegistry()
    catalog = MacroCatalog(registry)  # type: ignore[arg-type]
    registry.definitions = [
        definition("macro-a", display_name="Renamed Macro", class_name="RenamedClass")
    ]

    catalog.reload_macros()

    assert set(catalog.definitions_by_id) == {"macro-a"}
    assert catalog.get("macro-a").display_name == "Renamed Macro"


def test_macro_catalog_exposes_search_roots():
    catalog = MacroCatalog(FakeRegistry())  # type: ignore[arg-type]

    assert catalog.search_roots() == (
        Path("macros"),
        Path("examples") / "macros",
    )


def test_macro_browser_selection_returns_macro_id(qtbot):
    catalog = MacroCatalog(FakeRegistry())  # type: ignore[arg-type]
    widget = MacroBrowserPane(catalog)
    qtbot.addWidget(widget)

    widget.table.selectRow(0)

    assert widget.table.columnCount() == 1
    assert widget.table.horizontalHeaderItem(0).text() == "マクロ名"
    assert widget.table.item(0, 0).text() == "A Macro"
    assert widget.selected_macro_id() == "macro-a"
