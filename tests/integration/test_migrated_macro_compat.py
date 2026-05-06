import importlib
import inspect
import sys
import textwrap
from pathlib import Path

import pytest

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.executor import MacroExecutor


def _clear_macro_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "macros" or module_name.startswith("macros."):
            del sys.modules[module_name]


class RecordingCommand(Command):
    def __init__(self) -> None:
        self.logs: list[str] = []

    def press(self, *keys, dur=0.1, wait=0.1) -> None:
        self.logs.append(f"press:{keys}:{dur}:{wait}")

    def hold(self, *keys) -> None:
        self.logs.append(f"hold:{keys}")

    def release(self, *keys) -> None:
        self.logs.append(f"release:{keys}")

    def wait(self, wait: float) -> None:
        self.logs.append(f"wait:{wait}")

    def stop(self) -> None:
        self.logs.append("stop")

    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        self.logs.append(sep.join(map(str, values)) + end.rstrip("\n"))

    def capture(self, crop_region=None, grayscale: bool = False):
        self.logs.append(f"capture:{crop_region}:{grayscale}")
        return None

    def save_img(self, filename: str | Path, image) -> None:
        self.logs.append(f"save_img:{filename}:{image}")

    def load_img(self, filename: str | Path, grayscale: bool = False):
        self.logs.append(f"load_img:{filename}:{grayscale}")
        return None

    def keyboard(self, text: str) -> None:
        self.logs.append(f"keyboard:{text}")

    def type(self, key) -> None:
        self.logs.append(f"type:{key}")

    def notify(self, text: str, img=None) -> None:
        self.logs.append(f"notify:{text}:{img}")


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
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(tmp_path)
    _clear_macro_modules()
    return macros_dir


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

    executor = MacroExecutor()

    assert "ConventionPackageMacro" in executor.macros
    assert "ConventionSingleFileMacro" in executor.macros
    assert isinstance(executor.macros["ConventionPackageMacro"], MacroBase)
    assert isinstance(executor.macros["ConventionSingleFileMacro"], MacroBase)


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

    executor = MacroExecutor()

    assert "ManifestPackageMacro" in executor.macros
    assert isinstance(executor.macros["ManifestPackageMacro"], MacroBase)


def test_file_settings_and_exec_args_are_merged_with_exec_args_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    macros_dir = _prepare_temp_project(tmp_path, monkeypatch)
    (macros_dir / "settings_probe.py").write_text(
        textwrap.dedent(
            """
            from nyxpy.framework.core.macro.base import MacroBase
            from nyxpy.framework.core.macro.command import Command


            class SettingsProbeMacro(MacroBase):
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
    settings_dir = tmp_path / "static" / "settings_probe"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.toml").write_text(
        'value = "file"\nkeep = "file"\n',
        encoding="utf-8",
    )

    executor = MacroExecutor()
    executor.set_active_macro("SettingsProbeMacro")
    executor.execute(RecordingCommand(), {"value": "exec", "other": 3})

    assert executor.macro.args == {"value": "exec", "keep": "file", "other": 3}


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("macros.frlg_id_rng.macro", "FrlgIdRngMacro"),
        ("macros.frlg_initial_seed.macro", "FrlgInitialSeedMacro"),
        ("macros.frlg_gorgeous_resort.macro", "FrlgGorgeousResortMacro"),
        ("macros.frlg_wild_rng.macro", "FrlgWildRngMacro"),
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
