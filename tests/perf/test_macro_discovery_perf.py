from __future__ import annotations

import time
from pathlib import Path

from nyxpy.framework.core.macro.registry import MacroRegistry

MACRO_COUNT = 60
RELOAD_THRESHOLD_S = 2.0


def _write_macro(path: Path, index: int) -> None:
    package_dir = path / f"perf_macro_{index:03d}"
    package_dir.mkdir()
    class_name = f"PerfMacro{index:03d}"
    (package_dir / "macro.py").write_text(
        f"""from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class {class_name}(MacroBase):
    description = "perf macro"
    tags = ["perf"]

    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        pass

    def finalize(self, cmd: Command) -> None:
        pass
""",
        encoding="utf-8",
    )


def test_macro_registry_reload_perf(tmp_path: Path) -> None:
    macros_dir = tmp_path / "macros"
    macros_dir.mkdir()
    for index in range(MACRO_COUNT):
        _write_macro(macros_dir, index)

    registry = MacroRegistry(project_root=tmp_path)

    started = time.perf_counter()
    registry.reload()
    elapsed = time.perf_counter() - started

    assert len(registry.definitions) == MACRO_COUNT
    assert registry.diagnostics == ()
    assert elapsed < RELOAD_THRESHOLD_S
