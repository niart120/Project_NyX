from __future__ import annotations

import inspect
import sys
import textwrap
from pathlib import Path

from swbt import Button as SwbtButton

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig, resolve_controller_model
from nyxpy.framework.core.hardware.swbt.factory import SwbtControllerOutputPortFactory
from nyxpy.framework.core.hardware.swbt.session import DummySwbtControllerSession
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import MacroRegistry
from nyxpy.framework.core.runtime.builder import create_device_runtime_builder
from nyxpy.framework.core.runtime.context import ExecutionContext, RuntimeBuildRequest
from nyxpy.framework.core.runtime.result import RunStatus
from nyxpy.framework.core.runtime.runtime import MacroRuntime
from tests.support.fakes import FakeFrameSourcePort, FakeLoggerPort


class FrameFactory:
    def create(self, *, source, allow_dummy: bool, timeout_sec: float):
        return FakeFrameSourcePort()

    def close(self) -> None:
        pass


def test_swbt_runtime_runs_press_and_imu_with_dummy_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_swbt_macro(tmp_path, monkeypatch)
    registry = MacroRegistry(project_root=tmp_path)
    registry.reload()
    session = DummySwbtControllerSession()
    swbt_factory = SwbtControllerOutputPortFactory(session_factory=lambda _config: session)
    config = SwbtControllerConfig(
        model=resolve_controller_model("pro-controller"),
        adapter="dummy-adapter",
        key_store_path=tmp_path / ".nyxpy" / "swbt" / "pro-controller-bond.json",
    )
    builder = create_device_runtime_builder(
        project_root=tmp_path,
        registry=registry,
        controller_config=config,
        swbt_controller_factory=swbt_factory,
        frame_source_factory=FrameFactory(),
        notification_handler=None,
        logger=FakeLoggerPort(),
    )

    result = builder.run(RuntimeBuildRequest(macro_id="swbt_runtime_sample"))
    builder.shutdown()

    assert result.status is RunStatus.SUCCESS
    assert any(SwbtButton.A in state.buttons for state in session.states)
    assert any(state.imu_frames[0].gyro_x == 7 for state in session.states)
    assert session.closed is True


def test_command_runtime_context_do_not_import_swbt() -> None:
    surfaces = (Command, MacroRuntime, ExecutionContext)

    for surface in surfaces:
        assert "swbt" not in inspect.getsource(surface)


def _write_swbt_macro(project_root: Path, monkeypatch) -> None:
    macros_dir = project_root / "macros"
    package_dir = macros_dir / "swbt_runtime_sample"
    package_dir.mkdir(parents=True)
    monkeypatch.syspath_prepend(project_root)
    _clear_macro_modules()
    (package_dir / "__init__.py").write_text(
        "from .macro import SwbtRuntimeSample\n__all__ = ['SwbtRuntimeSample']\n",
        encoding="utf-8",
    )
    (package_dir / "macro.py").write_text(
        textwrap.dedent(
            """
            from nyxpy.framework.core.constants import Button, IMUFrame
            from nyxpy.framework.core.macro.base import MacroBase
            from nyxpy.framework.core.macro.command import Command


            class SwbtRuntimeSample(MacroBase):
                def initialize(self, cmd: Command, args: dict) -> None:
                    pass

                def run(self, cmd: Command) -> None:
                    cmd.press(Button.A, dur=0, wait=0)
                    cmd.imu(IMUFrame.gyro(x=7))

                def finalize(self, cmd: Command) -> None:
                    pass
            """
        ),
        encoding="utf-8",
    )


def _clear_macro_modules() -> None:
    for module_name in list(sys.modules):
        if module_name in {"macro", "macros"} or module_name.startswith(("macro.", "macros.")):
            del sys.modules[module_name]
