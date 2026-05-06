import sys
import textwrap
from pathlib import Path

import pytest

from nyxpy.framework.core.macro.registry import AmbiguousMacroError, MacroRegistry
from nyxpy.framework.core.settings.exceptions import ConfigurationError


def _prepare_project(tmp_path: Path) -> Path:
    macros_dir = tmp_path / "macros"
    macros_dir.mkdir()
    return macros_dir


def _write_macro_file(path: Path, class_name: str, *, body: str = "") -> None:
    body_block = textwrap.indent(textwrap.dedent(body).strip(), "    ")
    body_section = f"{body_block}\n" if body_block else ""
    path.write_text(
        f"""from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class {class_name}(MacroBase):
    description = "class description"
    tags = ["class-tag"]
{body_section}
    def initialize(self, cmd: Command, args: dict) -> None:
        self.args = dict(args)

    def run(self, cmd: Command) -> None:
        pass

    def finalize(self, cmd: Command) -> None:
        pass
""",
        encoding="utf-8",
    )


def _write_package(macros_dir: Path, package_name: str, class_name: str, *, body: str = "") -> Path:
    package_dir = macros_dir / package_name
    package_dir.mkdir()
    _write_macro_file(package_dir / "macro.py", class_name, body=body)
    return package_dir


def test_registry_requires_explicit_project_root() -> None:
    with pytest.raises(ValueError, match="project_root is required"):
        MacroRegistry()


def test_registry_loads_manifest_package_macro(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    package_dir = _write_package(macros_dir, "manifest_package", "ManifestPackageMacro")
    (package_dir / "macro.toml").write_text(
        textwrap.dedent(
            """
            [macro]
            id = "manifest_package"
            entrypoint = "macros.manifest_package.macro:ManifestPackageMacro"
            display_name = "Manifest Package"
            description = "manifest description"
            tags = ["manifest", "package"]
            settings = "settings.toml"
            """
        ),
        encoding="utf-8",
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("manifest_package")
    assert definition.id == "manifest_package"
    assert definition.display_name == "Manifest Package"
    assert definition.description == "manifest description"
    assert definition.tags == ("manifest", "package")
    assert definition.settings_path == "settings.toml"
    assert definition.manifest_path == package_dir / "macro.toml"
    assert definition.entrypoint_kind == "manifest"
    assert registry.diagnostics == ()


def test_registry_loads_manifest_single_file_macro(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "manifest_single.py", "ManifestSingleMacro")
    (macros_dir / "manifest_single.toml").write_text(
        textwrap.dedent(
            """
            [macro]
            id = "manifest_single"
            entrypoint = "macros.manifest_single:ManifestSingleMacro"
            """
        ),
        encoding="utf-8",
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("manifest_single")
    assert definition.class_name == "ManifestSingleMacro"
    assert definition.entrypoint_kind == "manifest"
    assert len(registry.definitions) == 1


def test_registry_rejects_missing_entrypoint(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    package_dir = _write_package(macros_dir, "missing_entrypoint", "MissingEntrypointMacro")
    (package_dir / "macro.toml").write_text(
        '[macro]\nid = "missing_entrypoint"\n',
        encoding="utf-8",
    )
    _write_macro_file(macros_dir / "valid_macro.py", "ValidMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert "valid_macro" in registry.definitions
    assert "missing_entrypoint" not in registry.definitions
    assert registry.diagnostics[0].error_type == "entrypoint_not_found"
    assert registry.diagnostics[0].macro_id == "missing_entrypoint"


def test_registry_loads_convention_package_macro(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_package(macros_dir, "convention_package", "ConventionPackageMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("convention_package")
    assert definition.class_name == "ConventionPackageMacro"
    assert definition.display_name == "ConventionPackageMacro"
    assert definition.description == "class description"
    assert definition.tags == ("class-tag",)
    assert definition.entrypoint_kind == "convention"


def test_registry_loads_convention_single_file_macro(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "single_file.py", "SingleFileMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("single_file")
    assert definition.class_name == "SingleFileMacro"
    assert definition.macro_root == macros_dir
    assert registry.resolve("SingleFileMacro") == definition


def test_registry_uses_class_metadata_when_manifest_absent(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(
        macros_dir / "metadata_macro.py",
        "MetadataMacro",
        body=textwrap.dedent(
            """
            macro_id = "metadata-id"
            display_name = "Metadata Display"
            settings_path = "settings.toml"
            """
        ),
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("metadata-id")
    assert definition.display_name == "Metadata Display"
    assert definition.settings_path == "settings.toml"


def test_registry_requires_manifest_when_convention_is_ambiguous(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    (macros_dir / "ambiguous.py").write_text(
        textwrap.dedent(
            """
            from nyxpy.framework.core.macro.base import MacroBase


            class FirstMacro(MacroBase):
                def initialize(self, cmd, args): pass
                def run(self, cmd): pass
                def finalize(self, cmd): pass


            class SecondMacro(MacroBase):
                def initialize(self, cmd, args): pass
                def run(self, cmd): pass
                def finalize(self, cmd): pass
            """
        ),
        encoding="utf-8",
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert registry.definitions == {}
    assert registry.diagnostics[0].error_type == "ambiguous_entrypoint"


def test_class_name_alias_is_available_when_unique(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "unique.py", "UniqueMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert registry.resolve("UniqueMacro").id == "unique"


def test_class_name_collision_requires_qualified_id(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "first.py", "DuplicatedMacro")
    _write_macro_file(macros_dir / "second.py", "DuplicatedMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert registry.resolve("first").class_name == "DuplicatedMacro"
    assert registry.resolve("second").class_name == "DuplicatedMacro"
    with pytest.raises(AmbiguousMacroError) as exc_info:
        registry.resolve("DuplicatedMacro")
    assert exc_info.value.candidates == ("first", "second")


def test_load_failure_is_reported_without_stopping_reload(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "valid.py", "ValidMacro")
    (macros_dir / "broken.py").write_text("raise RuntimeError('broken import')\n", encoding="utf-8")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert "valid" in registry.definitions
    assert len(registry.diagnostics) == 1
    assert registry.diagnostics[0].error_type == "module_import_error"
    assert "broken import" in registry.diagnostics[0].message


def test_registry_reload_restores_sys_path_even_on_import_error(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    (macros_dir / "broken.py").write_text("raise RuntimeError('broken import')\n", encoding="utf-8")
    before = list(sys.path)

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert sys.path == before


def test_registry_reload_preserves_preexisting_sys_path_entry(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "valid.py", "ValidMacro")
    sys.path.insert(0, str(tmp_path))
    try:
        registry = MacroRegistry(project_root=tmp_path)
        registry.reload()
        assert str(tmp_path) in sys.path
    finally:
        sys.path.remove(str(tmp_path))


def test_settings_without_explicit_source_returns_empty_dict(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "no_settings.py", "NoSettingsMacro")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert registry.get_settings(registry.resolve("no_settings")) == {}


def test_settings_static_lookup_is_not_supported(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(macros_dir / "legacy_settings.py", "LegacySettingsMacro")
    settings_dir = tmp_path / "static" / "legacy_settings"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.toml").write_text("value = 'legacy'\n", encoding="utf-8")

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    assert registry.get_settings(registry.resolve("legacy_settings")) == {}


def test_explicit_settings_path_resolution(tmp_path: Path) -> None:
    macros_dir = _prepare_project(tmp_path)
    package_dir = _write_package(macros_dir, "settings_macro", "SettingsMacro")
    (package_dir / "settings.toml").write_text("value = 'macro-root'\n", encoding="utf-8")
    (tmp_path / "project_settings.toml").write_text("value = 'project-root'\n", encoding="utf-8")
    (package_dir / "macro.toml").write_text(
        textwrap.dedent(
            """
            [macro]
            id = "settings_macro"
            entrypoint = "macros.settings_macro.macro:SettingsMacro"
            settings = "settings.toml"
            """
        ),
        encoding="utf-8",
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    definition = registry.resolve("settings_macro")
    assert registry.settings_resolver.resolve(definition).path == package_dir / "settings.toml"
    assert registry.get_settings(definition) == {"value": "macro-root"}

    project_definition = type(definition)(
        **{**definition.__dict__, "settings_path": "project:project_settings.toml"}
    )
    assert registry.settings_resolver.resolve(project_definition).path == (
        tmp_path / "project_settings.toml"
    )
    assert registry.get_settings(project_definition) == {"value": "project-root"}


@pytest.mark.parametrize("settings_path", [".. /bad.toml", "../bad.toml", "bad\\settings.toml", ""])
def test_settings_resolver_rejects_invalid_portable_path(
    tmp_path: Path, settings_path: str
) -> None:
    macros_dir = _prepare_project(tmp_path)
    _write_macro_file(
        macros_dir / "invalid_settings.py",
        "InvalidSettingsMacro",
        body=f"settings_path = {settings_path!r}",
    )

    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()

    with pytest.raises(ConfigurationError) as exc_info:
        registry.get_settings(registry.resolve("invalid_settings"))
    assert exc_info.value.code == "NYX_SETTINGS_PATH_INVALID"
