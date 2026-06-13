from pathlib import Path

from PySide6.QtCore import Qt

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


def definition(
    macro_id: str,
    *,
    display_name: str,
    macro_root: Path,
    class_name: str | None = None,
    description: str = "",
    tags: tuple[str, ...] = (),
) -> MacroDefinition:
    class_name = class_name or display_name.replace(" ", "")
    return MacroDefinition(
        id=macro_id,
        aliases=(class_name,),
        display_name=display_name,
        class_name=class_name,
        module_name="tests.gui.test_macro_browser_pane",
        macro_root=macro_root,
        source_path=macro_root / "macro.py",
        settings_path=None,
        description=description,
        tags=tags,
        factory=ClassMacroFactory(DummyMacro),
    )


class FakeRegistry:
    def __init__(self, macros_root: Path) -> None:
        self.macro_search_roots = (MacroSearchRoot(macros_root, macros_root.parent / "resources"),)
        self.definitions = [
            definition(
                "frlg-id",
                display_name="FRLG ID",
                macro_root=macros_root / "pokemon" / "frlg_id",
                description="initial seed search",
                tags=("pokemon", "rng"),
            ),
            definition(
                "timer",
                display_name="Timer",
                macro_root=macros_root / "timer",
                tags=("utility",),
            ),
        ]
        self.reloads = 0

    def reload(self) -> None:
        self.reloads += 1

    def list(self):
        return tuple(self.definitions)


def browser(qtbot, tmp_path: Path) -> tuple[MacroBrowserPane, FakeRegistry]:
    registry = FakeRegistry(tmp_path / "macros")
    catalog = MacroCatalog(registry)  # type: ignore[arg-type]
    widget = MacroBrowserPane(catalog)
    qtbot.addWidget(widget)
    return widget, registry


def test_macro_browser_defaults_to_explorer_view(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)

    assert widget.stack.currentWidget() is widget.explorer_tree
    assert widget.explorer_button.isChecked()
    assert not widget.search_button.isChecked()


def test_macro_browser_switches_to_search_view(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)
    widget.show()

    qtbot.mouseClick(widget.search_button, Qt.MouseButton.LeftButton)

    assert widget.stack.currentWidget() is widget.search_page
    qtbot.waitUntil(widget.search_input.hasFocus, timeout=1000)


def test_macro_browser_selection_returns_macro_id_in_explorer(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)

    item = widget._find_tree_item("frlg-id")
    assert item is not None
    widget.explorer_tree.setCurrentItem(item)

    assert widget.selected_macro_id() == "frlg-id"
    assert widget.selected_macro_display_name() == "FRLG ID"


def test_macro_browser_selection_returns_macro_id_in_search(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)

    widget.set_view_mode("search")
    widget.set_search_query("seed")
    widget.search_results.setCurrentRow(0)

    assert widget.selected_macro_id() == "frlg-id"


def test_macro_browser_folder_selection_is_not_runnable(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)
    selection_states: list[bool] = []
    widget.selection_changed.connect(selection_states.append)

    folder = widget.explorer_tree.topLevelItem(0)
    assert folder.text(0) == "pokemon"
    widget.explorer_tree.setCurrentItem(folder)

    assert widget.selected_macro_id() is None
    assert selection_states[-1] is False


def test_macro_browser_reload_preserves_mode_query_and_selection(qtbot, tmp_path: Path):
    widget, registry = browser(qtbot, tmp_path)
    widget.set_view_mode("search")
    widget.set_search_query("tag:rng")
    widget.search_results.setCurrentRow(0)

    qtbot.mouseClick(widget.reload_button, Qt.MouseButton.LeftButton)

    assert registry.reloads == 2
    assert widget.stack.currentWidget() is widget.search_page
    assert widget.search_input.text() == "tag:rng"
    assert widget.selected_macro_id() == "frlg-id"


def test_macro_browser_reload_clears_missing_selection(qtbot, tmp_path: Path):
    widget, registry = browser(qtbot, tmp_path)
    item = widget._find_tree_item("frlg-id")
    assert item is not None
    widget.explorer_tree.setCurrentItem(item)
    registry.definitions = [
        definition(
            "timer",
            display_name="Timer",
            macro_root=tmp_path / "macros" / "timer",
        )
    ]

    qtbot.mouseClick(widget.reload_button, Qt.MouseButton.LeftButton)

    assert widget.selected_macro_id() is None


def test_macro_browser_reload_clears_selection_when_search_no_longer_matches(
    qtbot,
    tmp_path: Path,
):
    widget, registry = browser(qtbot, tmp_path)
    widget.set_view_mode("search")
    widget.set_search_query("tag:rng")
    widget.search_results.setCurrentRow(0)
    registry.definitions = [
        definition(
            "frlg-id",
            display_name="FRLG ID",
            macro_root=tmp_path / "macros" / "pokemon" / "frlg_id",
            tags=("utility",),
        ),
        definition(
            "timer",
            display_name="Timer",
            macro_root=tmp_path / "macros" / "timer",
        ),
    ]

    qtbot.mouseClick(widget.reload_button, Qt.MouseButton.LeftButton)

    assert widget.stack.currentWidget() is widget.search_page
    assert widget.search_results.count() == 0
    assert widget.selected_macro_id() is None


def test_macro_browser_ctrl_f_focuses_search(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)
    widget.show()
    widget.setFocus()

    qtbot.keyClick(widget, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)

    assert widget.stack.currentWidget() is widget.search_page
    qtbot.waitUntil(widget.search_input.hasFocus, timeout=1000)


def test_macro_browser_search_escape_clears_or_returns_to_explorer(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)
    widget.set_view_mode("search")
    widget.search_input.setText("rng")

    qtbot.keyClick(widget.search_input, Qt.Key.Key_Escape)
    assert widget.search_input.text() == ""
    assert widget.stack.currentWidget() is widget.search_page

    qtbot.keyClick(widget.search_input, Qt.Key.Key_Escape)
    assert widget.stack.currentWidget() is widget.explorer_tree


def test_macro_browser_does_not_render_connection_state(qtbot, tmp_path: Path):
    widget, _registry = browser(qtbot, tmp_path)
    text = " ".join(button.text() for button in widget.findChildren(type(widget.reload_button)))

    assert "シリアル" not in text
    assert "映像" not in text
