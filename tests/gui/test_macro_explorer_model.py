from pathlib import Path

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.registry import ClassMacroFactory, MacroDefinition
from nyxpy.gui.macro_explorer_model import (
    MacroExplorerNode,
    build_explorer_tree,
    search_macros,
)


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
    return MacroDefinition(
        id=macro_id,
        aliases=(class_name or display_name.replace(" ", ""),),
        display_name=display_name,
        class_name=class_name or display_name.replace(" ", ""),
        module_name="tests.gui.test_macro_explorer_model",
        macro_root=macro_root,
        source_path=macro_root / "macro.py",
        settings_path=None,
        description=description,
        tags=tags,
        factory=ClassMacroFactory(DummyMacro),
    )


def test_build_explorer_tree_groups_by_macro_location(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition(
            "frlg-id",
            display_name="FRLG ID",
            macro_root=macros_root / "pokemon" / "frlg_id",
        ),
        definition("timer", display_name="Timer", macro_root=macros_root / "timer"),
    )

    tree = build_explorer_tree(definitions, (macros_root,))

    assert tree == (
        MacroExplorerNode(
            label="pokemon",
            macro_id=None,
            children=(MacroExplorerNode(label="FRLG ID", macro_id="frlg-id"),),
        ),
        MacroExplorerNode(label="Timer", macro_id="timer"),
    )


def test_build_explorer_tree_omits_single_root_label(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition("macro-a", display_name="A Macro", macro_root=macros_root / "macro_a"),
    )

    tree = build_explorer_tree(definitions, (macros_root,))

    assert tree == (MacroExplorerNode(label="A Macro", macro_id="macro-a"),)


def test_build_explorer_tree_keeps_multiple_root_labels(tmp_path: Path):
    workspace_root = tmp_path / "macros"
    examples_root = tmp_path / "examples" / "macros"
    definitions = (
        definition("local", display_name="Local Macro", macro_root=workspace_root / "local"),
        definition(
            "example",
            display_name="Example Macro",
            macro_root=examples_root / "example",
        ),
    )

    tree = build_explorer_tree(definitions, (workspace_root, examples_root))

    assert tree == (
        MacroExplorerNode(
            label="workspace",
            macro_id=None,
            children=(MacroExplorerNode(label="Local Macro", macro_id="local"),),
        ),
        MacroExplorerNode(
            label="examples",
            macro_id=None,
            children=(MacroExplorerNode(label="Example Macro", macro_id="example"),),
        ),
    )


def test_search_macros_matches_display_name_and_macro_id(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition("frlg-id", display_name="FRLG ID", macro_root=macros_root / "frlg_id"),
        definition("timer", display_name="Timer", macro_root=macros_root / "timer"),
    )

    by_name = search_macros(definitions, "frlg")
    by_id = search_macros(definitions, "timer")

    assert [result.macro_id for result in by_name] == ["frlg-id"]
    assert [result.macro_id for result in by_id] == ["timer"]


def test_search_macros_matches_description(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition(
            "rng",
            display_name="RNG Macro",
            macro_root=macros_root / "rng",
            description="initial seed search",
        ),
        definition("timer", display_name="Timer", macro_root=macros_root / "timer"),
    )

    results = search_macros(definitions, "seed")

    assert [result.macro_id for result in results] == ["rng"]
    assert results[0].score == 20


def test_search_macros_matches_tags(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition(
            "frlg",
            display_name="FRLG",
            macro_root=macros_root / "frlg",
            tags=("pokemon", "rng"),
        ),
    )

    results = search_macros(definitions, "poke")

    assert [result.macro_id for result in results] == ["frlg"]
    assert results[0].matched_tags == ("pokemon",)


def test_search_macros_supports_tag_filter(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition(
            "tagged",
            display_name="Unrelated Name",
            macro_root=macros_root / "tagged",
            description="not searched by tag filter",
            tags=("rng",),
        ),
        definition(
            "description-only",
            display_name="RNG by Description",
            macro_root=macros_root / "description_only",
            description="rng",
        ),
    )

    tag_results = search_macros(definitions, "tag:rng")
    hash_results = search_macros(definitions, "#rng")

    assert [result.macro_id for result in tag_results] == ["tagged"]
    assert [result.macro_id for result in hash_results] == ["tagged"]


def test_search_macros_uses_and_between_tokens(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition(
            "frlg-id",
            display_name="FRLG ID",
            macro_root=macros_root / "frlg_id",
            tags=("rng",),
        ),
        definition(
            "frlg-timer",
            display_name="FRLG Timer",
            macro_root=macros_root / "frlg_timer",
            tags=("timer",),
        ),
    )

    results = search_macros(definitions, "frlg tag:rng")

    assert [result.macro_id for result in results] == ["frlg-id"]


def test_search_macros_orders_by_score_then_display_name(tmp_path: Path):
    macros_root = tmp_path / "macros"
    definitions = (
        definition("partial", display_name="FRLG Timer", macro_root=macros_root / "partial"),
        definition("exact", display_name="FRLG", macro_root=macros_root / "exact"),
        definition("prefix", display_name="FRLG ID", macro_root=macros_root / "prefix"),
    )

    results = search_macros(definitions, "frlg")

    assert [result.macro_id for result in results] == ["exact", "prefix", "partial"]
