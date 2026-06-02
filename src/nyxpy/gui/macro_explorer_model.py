"""GUI macro explorer の表示モデル。"""

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.macro.registry import MacroDefinition


@dataclass(frozen=True)
class MacroLocation:
    """Explorer view 上の macro 配置情報。"""

    root_label: str
    relative_parts: tuple[str, ...]


@dataclass(frozen=True)
class MacroExplorerNode:
    """Explorer view の folder または macro leaf。"""

    label: str
    macro_id: str | None
    children: tuple["MacroExplorerNode", ...] = ()


@dataclass(frozen=True)
class MacroSearchResult:
    """Search view の 1 件分の結果。"""

    macro_id: str
    display_name: str
    score: int
    matched_tags: tuple[str, ...]


def location_for_definition(
    definition: MacroDefinition,
    roots: tuple[Path, ...],
) -> MacroLocation:
    """MacroDefinition から Explorer 用 location を算出する。"""
    root_paths = tuple(Path(root).resolve() for root in roots)
    macro_root = Path(definition.macro_root).resolve()
    matched_index, matched_root = _best_matching_root(macro_root, root_paths)
    if matched_root is None:
        matched_root = macro_root.parent
        matched_index = 0
    label = _root_label(matched_root, matched_index)
    try:
        relative_parts = macro_root.relative_to(matched_root).parts
    except ValueError:
        relative_parts = ()
    if relative_parts and _is_package_definition(definition):
        relative_parts = relative_parts[:-1]
    return MacroLocation(root_label=label, relative_parts=tuple(relative_parts))


def build_explorer_tree(
    definitions: tuple[MacroDefinition, ...],
    roots: tuple[Path, ...],
) -> tuple[MacroExplorerNode, ...]:
    """MacroDefinition の一覧から Explorer tree を構築する。"""
    show_root = len(roots) > 1
    root_entries: dict[str, dict] = {}
    root_order: list[str] = []
    if show_root:
        for index, root in enumerate(roots):
            root_order.append(_root_label(Path(root).resolve(), index))
    for definition in _sorted_definitions(definitions):
        location = location_for_definition(definition, roots)
        root_key = location.root_label
        if root_key not in root_entries:
            root_entries[root_key] = {"folders": {}, "leaves": []}
            if root_key not in root_order:
                root_order.append(root_key)
        current = root_entries[root_key]
        for part in location.relative_parts:
            folders = current["folders"]
            if part not in folders:
                folders[part] = {"folders": {}, "leaves": []}
            current = folders[part]
        current["leaves"].append(
            MacroExplorerNode(label=definition.display_name, macro_id=definition.id)
        )

    if show_root:
        return tuple(
            MacroExplorerNode(
                label=root_label,
                macro_id=None,
                children=_nodes_from_entry(root_entries[root_label]),
            )
            for root_label in root_order
            if root_label in root_entries
        )
    merged = {"folders": {}, "leaves": []}
    for root_label in root_order:
        entry = root_entries[root_label]
        _merge_entry(merged, entry)
    return _nodes_from_entry(merged)


def search_macros(
    definitions: tuple[MacroDefinition, ...],
    query: str,
) -> tuple[MacroSearchResult, ...]:
    """Query に一致する macro を score 順で返す。"""
    tokens = _search_tokens(query)
    if not tokens:
        return tuple(
            MacroSearchResult(definition.id, definition.display_name, 0, ())
            for definition in _sorted_definitions(definitions)
        )

    results: list[MacroSearchResult] = []
    for definition in definitions:
        total_score = 0
        matched_tags: set[str] = set()
        matched = True
        for token in tokens:
            score, token_tags = _score_token(definition, token)
            if score <= 0:
                matched = False
                break
            total_score += score
            matched_tags.update(token_tags)
        if matched:
            results.append(
                MacroSearchResult(
                    macro_id=definition.id,
                    display_name=definition.display_name,
                    score=total_score,
                    matched_tags=tuple(sorted(matched_tags, key=str.casefold)),
                )
            )
    return tuple(
        sorted(
            results,
            key=lambda result: (-result.score, result.display_name.casefold(), result.macro_id),
        )
    )


def _best_matching_root(
    macro_root: Path,
    roots: tuple[Path, ...],
) -> tuple[int, Path | None]:
    matches: list[tuple[int, int, Path]] = []
    for index, root in enumerate(roots):
        try:
            relative = macro_root.relative_to(root)
        except ValueError:
            continue
        matches.append((len(relative.parts), index, root))
    if not matches:
        return 0, None
    _, index, root = min(matches)
    return index, root


def _root_label(root: Path, index: int) -> str:
    if root.name == "macros":
        if root.parent.name == "examples":
            return "examples"
        if index == 0:
            return "workspace"
    return root.name or str(root)


def _is_package_definition(definition: MacroDefinition) -> bool:
    source_path = Path(definition.source_path)
    return source_path.parent == Path(definition.macro_root) and source_path.name in {
        "__init__.py",
        "macro.py",
    }


def _nodes_from_entry(entry: dict) -> tuple[MacroExplorerNode, ...]:
    folder_nodes = [
        MacroExplorerNode(label=label, macro_id=None, children=_nodes_from_entry(child))
        for label, child in sorted(entry["folders"].items(), key=lambda item: item[0].casefold())
    ]
    leaf_nodes = sorted(
        entry["leaves"],
        key=lambda node: (node.label.casefold(), node.macro_id or ""),
    )
    return tuple(folder_nodes + leaf_nodes)


def _merge_entry(target: dict, source: dict) -> None:
    target["leaves"].extend(source["leaves"])
    for label, source_child in source["folders"].items():
        target_child = target["folders"].setdefault(label, {"folders": {}, "leaves": []})
        _merge_entry(target_child, source_child)


def _sorted_definitions(definitions: tuple[MacroDefinition, ...]) -> tuple[MacroDefinition, ...]:
    return tuple(
        sorted(
            definitions,
            key=lambda definition: (definition.display_name.casefold(), definition.id),
        )
    )


def _search_tokens(query: str) -> tuple[tuple[str, bool], ...]:
    tokens: list[tuple[str, bool]] = []
    for raw_token in query.casefold().split():
        token = raw_token.strip()
        if not token:
            continue
        if token.startswith("tag:"):
            value = token[4:]
            if value:
                tokens.append((value, True))
        elif token.startswith("#"):
            value = token[1:]
            if value:
                tokens.append((value, True))
        else:
            tokens.append((token, False))
    return tuple(tokens)


def _score_token(
    definition: MacroDefinition,
    token: tuple[str, bool],
) -> tuple[int, tuple[str, ...]]:
    text, tag_only = token
    matched_tags = _matching_tags(definition.tags, text)
    tag_score = _tag_score(matched_tags, text)
    if tag_only:
        return tag_score, matched_tags
    name_score = max(
        _text_score(definition.display_name, text),
        _text_score(definition.id, text),
        _text_score(definition.class_name, text),
    )
    description_score = 20 if text in definition.description.casefold() else 0
    return max(name_score, tag_score, description_score), matched_tags


def _text_score(value: str, token: str) -> int:
    text = value.casefold()
    if text == token:
        return 100
    if text.startswith(token):
        return 80
    if token in text:
        return 30
    return 0


def _matching_tags(tags: tuple[str, ...], token: str) -> tuple[str, ...]:
    return tuple(tag for tag in tags if token in tag.casefold())


def _tag_score(matched_tags: tuple[str, ...], token: str) -> int:
    if any(tag.casefold() == token for tag in matched_tags):
        return 70
    if any(tag.casefold().startswith(token) for tag in matched_tags):
        return 50
    if matched_tags:
        return 30
    return 0
