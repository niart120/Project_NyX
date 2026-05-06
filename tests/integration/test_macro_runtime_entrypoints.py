import importlib
from pathlib import Path

import pytest


@pytest.mark.xfail(
    strict=True,
    reason="MacroRuntime is introduced before GUI/CLI migration in later phases.",
)
def test_macro_runtime_module_is_available_for_entrypoints() -> None:
    importlib.import_module("nyxpy.framework.core.runtime")


@pytest.mark.xfail(
    strict=True,
    reason="CLI and GUI stop importing MacroExecutor after runtime adapter migration.",
)
def test_gui_cli_entrypoints_do_not_import_macro_executor() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    entrypoint_sources = [
        repo_root / "src" / "nyxpy" / "cli" / "run_cli.py",
        repo_root / "src" / "nyxpy" / "gui" / "main_window.py",
    ]

    for source_path in entrypoint_sources:
        assert "MacroExecutor" not in source_path.read_text(encoding="utf-8")
