from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.result import RunStatus
from nyxpy.framework.core.runtime.runtime import MacroRuntime
from tests.support.fake_execution_context import make_fake_execution_context
from tests.support.fakes import FakeFrameSourcePort


@dataclass(frozen=True)
class Factory:
    macro: MacroBase

    def create(self) -> MacroBase:
        return self.macro


class Registry:
    def __init__(self, definition: MacroDefinition) -> None:
        self.definition = definition
        self.resolved: list[str] = []

    def resolve(self, name_or_id: str) -> MacroDefinition:
        self.resolved.append(name_or_id)
        return self.definition


class RecordingMacro(MacroBase):
    description = "recording"
    tags = ["test"]

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.args = {}

    def initialize(self, cmd: Command, args: dict) -> None:
        self.calls.append("initialize")
        self.args = args

    def run(self, cmd: Command) -> None:
        self.calls.append("run")
        cmd.press("A", dur=0, wait=0)

    def finalize(self, cmd: Command) -> None:
        self.calls.append("finalize")


class NotReadyFrameSource(FakeFrameSourcePort):
    def await_ready(self, timeout: float) -> bool:
        return False


class FailingCloseFrameSource(FakeFrameSourcePort):
    def close(self) -> None:
        raise RuntimeError("close failed")


def definition_for(macro: MacroBase) -> MacroDefinition:
    return MacroDefinition(
        id="sample",
        aliases=("sample", "RecordingMacro"),
        display_name="Sample",
        class_name=type(macro).__name__,
        module_name="tests.sample",
        macro_root=Path(__file__).parent,
        source_path=Path(__file__),
        settings_path=None,
        description="",
        tags=(),
        factory=Factory(macro),
    )


def test_macro_runtime_run_delegates_to_runner_and_closes_ports(tmp_path) -> None:
    macro = RecordingMacro()
    context = make_fake_execution_context(tmp_path, exec_args={"x": 1})
    runtime = MacroRuntime(Registry(definition_for(macro)))

    result = runtime.run(context)

    assert result.status is RunStatus.SUCCESS
    assert macro.calls == ["initialize", "run", "finalize"]
    assert macro.args == {"x": 1}
    assert context.controller.closed is True
    assert context.frame_source.closed is True


def test_macro_runtime_pre_run_frame_not_ready_returns_failed_result(tmp_path) -> None:
    macro = RecordingMacro()
    context = make_fake_execution_context(tmp_path, frame_source=NotReadyFrameSource())
    runtime = MacroRuntime(Registry(definition_for(macro)))

    result = runtime.run(context)

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "NYX_FRAME_NOT_READY"
    assert macro.calls == []


def test_macro_runtime_adds_cleanup_warnings_without_overwriting_status(tmp_path) -> None:
    macro = RecordingMacro()
    context = make_fake_execution_context(tmp_path, frame_source=FailingCloseFrameSource())
    runtime = MacroRuntime(Registry(definition_for(macro)))

    result = runtime.run(context)

    assert result.status is RunStatus.SUCCESS
    assert result.cleanup_warnings[0].port_name == "frame_source"
    assert result.cleanup_warnings[0].message == "close failed"


def test_run_handle_wait_done_result_contract(tmp_path) -> None:
    macro = RecordingMacro()
    context = make_fake_execution_context(tmp_path)
    runtime = MacroRuntime(Registry(definition_for(macro)))

    handle = runtime.start(context)

    assert handle.wait(1.0) is True
    assert handle.done() is True
    assert handle.result().status is RunStatus.SUCCESS


def test_run_handle_cancel_requests_token(tmp_path) -> None:
    context = make_fake_execution_context(tmp_path)
    runtime = MacroRuntime(Registry(definition_for(RecordingMacro())))

    handle = runtime.start(context)
    handle.cancel()
    handle.wait(1.0)

    assert context.cancellation_token.stop_requested()
    assert context.cancellation_token.reason() == "user cancelled"
    assert context.cancellation_token.source() == "gui_or_cli"
