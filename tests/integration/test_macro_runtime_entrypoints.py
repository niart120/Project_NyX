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
    from nyxpy.gui.app_services import GuiAppServices
    from nyxpy.gui.main_window import MainWindow

    cli_source = inspect.getsource(create_runtime_builder)
    gui_source = inspect.getsource(GuiAppServices._replace_runtime_builder) + inspect.getsource(
        MainWindow._start_macro
    )

    assert "get_active_device" not in cli_source
    assert "auto_register_devices" not in cli_source
    assert "get_active_device" not in gui_source
    assert "create_device_runtime_builder" not in inspect.getsource(MainWindow)


def test_virtual_controller_model_uses_controller_output_port() -> None:
    from nyxpy.gui.models.virtual_controller_model import VirtualControllerModel

    source = inspect.getsource(VirtualControllerModel)

    assert "ControllerOutputPort" in source
    assert ".send(" not in source


def test_gui_has_no_event_bus_module() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    gui_root = repo_root / "src" / "nyxpy" / "gui"

    assert not (gui_root / "events.py").exists()
    for source_path in gui_root.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert "EventBus" not in source
        assert "EventType" not in source
