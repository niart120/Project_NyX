from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.macro.scaffold import (
    MacroScaffoldConflictError,
    ScaffoldConflictPolicy,
    create_macro_scaffold,
    validate_macro_id,
)
from nyxpy.framework.core.settings.workspace import ensure_workspace


def test_scaffold_templates_are_packaged() -> None:
    template_root = resources.files("nyxpy.templates.macro")

    for name in (
        "__init__.py.template",
        "macro.py.template",
        "config.py.template",
        "test_logic.py.template",
        "settings.toml.template",
    ):
        assert template_root.joinpath(name).read_text(encoding="utf-8")


def test_create_macro_scaffold_creates_standard_layout(tmp_path: Path) -> None:
    ensure_workspace(tmp_path)

    result = create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    created = {path.relative_to(tmp_path) for path in result.created}
    assert Path("macros/sample_turbo/__init__.py") in created
    assert Path("macros/sample_turbo/macro.py") in created
    assert Path("macros/sample_turbo/config.py") in created
    assert Path("macros/sample_turbo/test_logic.py") in created
    assert Path("resources/sample_turbo/settings.toml") in created
    assert (tmp_path / "resources" / "sample_turbo" / "assets").is_dir()
    assert "class SampleTurboMacro" in (
        tmp_path / "macros" / "sample_turbo" / "macro.py"
    ).read_text(encoding="utf-8")


def test_create_macro_scaffold_requires_existing_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="NyX workspace not found"):
        create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    assert not (tmp_path / "macros").exists()


def test_create_macro_scaffold_rejects_invalid_macro_id() -> None:
    for macro_id in ("Sample", "_sample", "class", "test", "bad-name"):
        with pytest.raises(ValueError, match="Invalid macro_id"):
            validate_macro_id(macro_id)


def test_create_macro_scaffold_reports_conflicts(tmp_path: Path) -> None:
    ensure_workspace(tmp_path)
    create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    with pytest.raises(MacroScaffoldConflictError) as exc_info:
        create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    assert tmp_path / "macros" / "sample_turbo" / "macro.py" in exc_info.value.conflicts


def test_create_macro_scaffold_can_skip_existing_files(tmp_path: Path) -> None:
    ensure_workspace(tmp_path)
    create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    result = create_macro_scaffold(
        macro_id="sample_turbo",
        project_root=tmp_path,
        conflict_policy=ScaffoldConflictPolicy.SKIP,
    )

    assert result.created == ()
    assert tmp_path / "macros" / "sample_turbo" / "macro.py" in result.skipped


def test_create_macro_scaffold_registry_can_load_generated_macro(tmp_path: Path) -> None:
    ensure_workspace(tmp_path)
    create_macro_scaffold(macro_id="sample_turbo", project_root=tmp_path)

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()
    definition = registry.resolve("sample_turbo")
    settings = registry.get_settings(definition)

    assert definition.class_name == "SampleTurboMacro"
    assert definition.settings_path == "resource:settings.toml"
    assert settings["count"] == 10
