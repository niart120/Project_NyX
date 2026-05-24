"""マクロ雛形の生成サービス。"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path

from nyxpy.framework.core.macro.exceptions import ConfigurationError
from nyxpy.framework.core.settings.workspace import resolve_project_root

_MACRO_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED_MACRO_IDS = {
    "__init__",
    "macro",
    "macros",
    "os",
    "sys",
    "test",
    "typing",
}
_TEMPLATE_PACKAGE = "nyxpy.templates.macro"
_TEMPLATE_FILES = {
    "__init__.py.template": Path("macros") / "{macro_id}" / "__init__.py",
    "macro.py.template": Path("macros") / "{macro_id}" / "macro.py",
    "config.py.template": Path("macros") / "{macro_id}" / "config.py",
    "test_logic.py.template": Path("macros") / "{macro_id}" / "test_logic.py",
    "settings.toml.template": Path("resources") / "{macro_id}" / "settings.toml",
}


class ScaffoldConflictPolicy(StrEnum):
    """既存ファイルと衝突した場合の扱い。"""

    FAIL = "fail"
    SKIP = "skip"
    OVERWRITE = "overwrite"


class MacroScaffoldError(ConfigurationError):
    """マクロ雛形生成に失敗したことを表す例外。"""


class MacroScaffoldConflictError(MacroScaffoldError):
    """既存ファイルとの衝突で雛形生成できない場合の例外。"""

    def __init__(self, conflicts: list[Path], project_root: Path) -> None:
        """衝突した path 一覧を保持して初期化します。"""
        self.conflicts = tuple(conflicts)
        conflict_text = ", ".join(str(path.relative_to(project_root)) for path in conflicts)
        super().__init__(
            f"Macro scaffold files already exist: {conflict_text}",
            code="NYX_MACRO_SCAFFOLD_CONFLICT",
            component="MacroScaffold",
            details={"conflicts": [str(path) for path in conflicts]},
        )


@dataclass(frozen=True)
class MacroScaffoldResult:
    """雛形生成で作成、上書き、skip した path 一覧。"""

    macro_id: str
    project_root: Path
    created: tuple[Path, ...]
    overwritten: tuple[Path, ...]
    skipped: tuple[Path, ...]


def create_macro_scaffold(
    *,
    macro_id: str,
    project_root: Path | None = None,
    conflict_policy: ScaffoldConflictPolicy = ScaffoldConflictPolicy.FAIL,
) -> MacroScaffoldResult:
    """既存 workspace に macro 個別 scaffold を生成します。

    Args:
        macro_id: 作成するマクロ ID。小文字スネークケースを要求します。
        project_root: workspace root。未指定の場合は現在位置から探索します。
        conflict_policy: 既存ファイルと衝突した場合の扱い。

    Returns:
        作成、上書き、skip した path 一覧。

    Raises:
        ConfigurationError: workspace が存在しない、または macro_id が不正な場合。
        MacroScaffoldConflictError: 既存ファイルと衝突した場合。

    """
    validate_macro_id(macro_id)
    root = resolve_project_root(explicit_root=project_root, allow_current_as_new=False)
    if not (root / ".nyxpy").is_dir():
        raise ConfigurationError(
            "NyX workspace not found. Run `nyxpy init` in the project root.",
            code="NYX_WORKSPACE_NOT_FOUND",
            component="MacroScaffold",
            details={"project_root": str(root)},
        )

    render_context = {
        "macro_id": macro_id,
        "class_name": _class_name_for_macro_id(macro_id),
    }
    planned_files = _planned_files(root, macro_id)
    conflicts = [path for path in planned_files.values() if path.exists()]
    if conflicts and conflict_policy is ScaffoldConflictPolicy.FAIL:
        raise MacroScaffoldConflictError(conflicts, root)

    created: list[Path] = []
    overwritten: list[Path] = []
    skipped: list[Path] = []
    (root / "resources" / macro_id / "assets").mkdir(parents=True, exist_ok=True)

    for template_name, output_path in planned_files.items():
        if output_path.exists():
            if conflict_policy is ScaffoldConflictPolicy.SKIP:
                skipped.append(output_path)
                continue
            overwritten.append(output_path)
        else:
            created.append(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            _read_template(template_name).format(**render_context),
            encoding="utf-8",
        )

    return MacroScaffoldResult(
        macro_id=macro_id,
        project_root=root,
        created=tuple(created),
        overwritten=tuple(overwritten),
        skipped=tuple(skipped),
    )


def validate_macro_id(macro_id: str) -> None:
    """macro_id が scaffold 生成可能な識別子か確認します。"""
    if (
        not _MACRO_ID_PATTERN.fullmatch(macro_id)
        or keyword.iskeyword(macro_id)
        or macro_id.startswith("_")
        or macro_id in _RESERVED_MACRO_IDS
    ):
        raise ConfigurationError(
            f"Invalid macro_id: {macro_id!r}. Use lower_snake_case like sample_macro.",
            code="NYX_MACRO_ID_INVALID",
            component="MacroScaffold",
            details={"macro_id": macro_id},
        )


def _planned_files(project_root: Path, macro_id: str) -> dict[str, Path]:
    return {
        template_name: project_root / Path(str(relative_path).format(macro_id=macro_id))
        for template_name, relative_path in _TEMPLATE_FILES.items()
    }


def _read_template(template_name: str) -> str:
    return resources.files(_TEMPLATE_PACKAGE).joinpath(template_name).read_text(encoding="utf-8")


def _class_name_for_macro_id(macro_id: str) -> str:
    class_name = "".join(part.capitalize() for part in macro_id.split("_"))
    return class_name if class_name.lower().endswith("macro") else f"{class_name}Macro"
