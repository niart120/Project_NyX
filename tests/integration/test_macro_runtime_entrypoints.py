import importlib
import inspect
import sys
from pathlib import Path


def test_macro_runtime_module_is_available_for_entrypoints() -> None:
    importlib.import_module("nyxpy.framework.core.runtime")


def test_gui_cli_entrypoints_do_not_import_macro_executor() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    entrypoint_sources = [
        repo_root / "src" / "nyxpy" / "cli" / "run_cli.py",
        repo_root / "src" / "nyxpy" / "gui" / "main_window.py",
    ]

    for source_path in entrypoint_sources:
        assert "MacroExecutor" not in source_path.read_text(encoding="utf-8")

    sys.modules.pop("nyxpy.framework.core.macro.executor", None)
    importlib.import_module("nyxpy.cli.run_cli")
    importlib.import_module("nyxpy.gui.main_window")

    assert "nyxpy.framework.core.macro.executor" not in sys.modules


def test_gui_cli_runtime_builder_paths_do_not_resolve_devices_directly() -> None:
    from nyxpy.cli.run_cli import create_runtime_builder
    from nyxpy.gui.main_window import MainWindow

    cli_source = inspect.getsource(create_runtime_builder)
    gui_source = inspect.getsource(MainWindow._create_runtime_builder)

    assert "get_active_device" not in cli_source
    assert "auto_register_devices" not in cli_source
    assert "get_active_device" not in gui_source
