import importlib
import inspect
import sys
import textwrap
from pathlib import Path

import pytest

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import MacroRuntimeBuilder
from nyxpy.framework.core.runtime.context import RuntimeBuildRequest
from tests.support.fake_execution_context import make_fake_execution_context
from tests.support.fakes import (
    FakeControllerOutputPort,
    FakeFrameSourcePort,
    FakeLoggerPort,
    FakeNotificationPort,
)


def _clear_macro_modules() -> None:
    for module_name in list(sys.modules):
        if module_name in {"macro", "macros"} or module_name.startswith(("macro.", "macros.")):
            del sys.modules[module_name]


def _write_macro_package(macros_dir: Path, package_name: str, class_name: str) -> None:
    package_dir = macros_dir / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        f"from .macro import {class_name}\n__all__ = ['{class_name}']\n",
        encoding="utf-8",
    )
    (package_dir / "macro.py").write_text(
        textwrap.dedent(
            f"""
            from nyxpy.framework.core.macro.base import MacroBase
            from nyxpy.framework.core.macro.command import Command


            class {class_name}(MacroBase):
                description = "{package_name}"
                tags = ["test"]

                def initialize(self, cmd: Command, args: dict) -> None:
                    self.args = dict(args)

                def run(self, cmd: Command) -> None:
                    cmd.log("{class_name}.run")

                def finalize(self, cmd: Command) -> None:
                    cmd.log("{class_name}.finalize")
            """
        ),
        encoding="utf-8",
    )


def _prepare_temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    macros_dir = tmp_path / "macros"
    macros_dir.mkdir()
    monkeypatch.syspath_prepend(tmp_path)
    _clear_macro_modules()
    return macros_dir


def _reloaded_registry(project_root: Path) -> MacroRegistry:
    registry = MacroRegistry(project_root=project_root)
    registry.reload()
    return registry


def _fake_builder(project_root: Path, registry: MacroRegistry) -> MacroRuntimeBuilder:
    base_context = make_fake_execution_context(project_root)
    return MacroRuntimeBuilder(
        project_root=project_root,
        registry=registry,
        controller_factory=lambda _request, _definition: FakeControllerOutputPort(),
        frame_source_factory=lambda _request, _definition: FakeFrameSourcePort(),
        resource_store_factory=lambda _request, _definition: base_context.resources,
        artifact_store_factory=lambda _request, _definition, _run_id: base_context.artifacts,
        notification_factory=lambda _request, _definition: FakeNotificationPort(),
        logger_factory=lambda _request, _definition: FakeLoggerPort(),
    )


def test_convention_package_and_single_file_macros_load_without_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    macros_dir = _prepare_temp_project(tmp_path, monkeypatch)
    _write_macro_package(macros_dir, "convention_package", "ConventionPackageMacro")
    (macros_dir / "convention_single_file.py").write_text(
        textwrap.dedent(
            """
            from nyxpy.framework.core.macro.base import MacroBase
            from nyxpy.framework.core.macro.command import Command


            class ConventionSingleFileMacro(MacroBase):
                def initialize(self, cmd: Command, args: dict) -> None:
                    self.args = dict(args)

                def run(self, cmd: Command) -> None:
                    cmd.log("single.run")

                def finalize(self, cmd: Command) -> None:
                    cmd.log("single.finalize")
            """
        ),
        encoding="utf-8",
    )

    registry = _reloaded_registry(tmp_path)

    assert registry.resolve("ConventionPackageMacro").id == "convention_package"
    assert registry.resolve("ConventionSingleFileMacro").id == "convention_single_file"
    assert isinstance(registry.create("ConventionPackageMacro"), MacroBase)
    assert isinstance(registry.create("ConventionSingleFileMacro"), MacroBase)


def test_optional_manifest_file_does_not_break_package_macro_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    macros_dir = _prepare_temp_project(tmp_path, monkeypatch)
    _write_macro_package(macros_dir, "manifest_package", "ManifestPackageMacro")
    (macros_dir / "manifest_package" / "macro.toml").write_text(
        textwrap.dedent(
            """
            [macro]
            id = "manifest_package"
            entrypoint = "macros.manifest_package.macro:ManifestPackageMacro"
            display_name = "Manifest Package"
            settings = "settings.toml"
            """
        ),
        encoding="utf-8",
    )

    registry = _reloaded_registry(tmp_path)

    definition = registry.resolve("manifest_package")
    assert definition.class_name == "ManifestPackageMacro"
    assert isinstance(registry.create("manifest_package"), MacroBase)


def test_file_settings_and_exec_args_are_merged_with_exec_args_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    macros_dir = _prepare_temp_project(tmp_path, monkeypatch)
    package_dir = macros_dir / "settings_probe"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "from .macro import SettingsProbeMacro\n__all__ = ['SettingsProbeMacro']\n",
        encoding="utf-8",
    )
    (package_dir / "macro.py").write_text(
        textwrap.dedent(
            """
            from nyxpy.framework.core.macro.base import MacroBase
            from nyxpy.framework.core.macro.command import Command


            class SettingsProbeMacro(MacroBase):
                settings_path = "settings.toml"

                def initialize(self, cmd: Command, args: dict) -> None:
                    self.args = dict(args)

                def run(self, cmd: Command) -> None:
                    cmd.log("settings_probe.run")

                def finalize(self, cmd: Command) -> None:
                    cmd.log("settings_probe.finalize")
            """
        ),
        encoding="utf-8",
    )
    (package_dir / "settings.toml").write_text(
        'value = "file"\nkeep = "file"\n',
        encoding="utf-8",
    )
    registry = _reloaded_registry(tmp_path)
    builder = _fake_builder(tmp_path, registry)

    context = builder.build(
        RuntimeBuildRequest(macro_id="settings_probe", exec_args={"value": "exec", "other": 3})
    )

    assert context.exec_args == {"value": "exec", "keep": "file", "other": 3}


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("macro.frlg_id_rng.macro", "FrlgIdRngMacro"),
        ("macro.frlg_initial_seed.macro", "FrlgInitialSeedMacro"),
        ("macro.frlg_gorgeous_resort.macro", "FrlgGorgeousResortMacro"),
        ("macro.frlg_wild_rng.macro", "FrlgWildRngMacro"),
    ],
)
def test_repository_representative_macros_keep_lifecycle_contract(
    module_name: str, class_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(repo_root)
    _clear_macro_modules()

    module = importlib.import_module(module_name)
    macro_cls = getattr(module, class_name)

    assert issubclass(macro_cls, MacroBase)
    assert list(inspect.signature(macro_cls.initialize).parameters) == ["self", "cmd", "args"]
    assert list(inspect.signature(macro_cls.run).parameters) == ["self", "cmd"]
    assert list(inspect.signature(macro_cls.finalize).parameters) == ["self", "cmd"]
