import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.result import RunStatus
from nyxpy.framework.core.runtime.runtime import MacroRuntime
from tests.support.fake_execution_context import make_fake_execution_context
from tests.support.fakes import FakeFullCapabilityController


@dataclass(frozen=True)
class Factory:
    macro: MacroBase

    def create(self) -> MacroBase:
        return self.macro


class Registry:
    def __init__(self, macros: dict[str, MacroBase]) -> None:
        self.macros = macros

    def resolve(self, name_or_id: str) -> MacroDefinition:
        macro = self.macros[name_or_id]
        return MacroDefinition(
            id=name_or_id,
            aliases=(name_or_id, type(macro).__name__),
            display_name=name_or_id,
            class_name=type(macro).__name__,
            module_name="tests.integration",
            macro_root=Path(__file__).parent,
            source_path=Path(__file__),
            settings_path=None,
            description="",
            tags=(),
            factory=Factory(macro),
        )


class DummyMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("Initializing DummyMacro", level="INFO")

    def run(self, cmd: Command) -> None:
        cmd.press(Button.A, dur=0, wait=0)
        cmd.keyboard("Hello")
        self.captured_frame = cmd.capture()

    def finalize(self, cmd: Command) -> None:
        cmd.release(Button.A)
        cmd.log("Finalizing DummyMacro", level="INFO")


class LongRunningMacro(MacroBase):
    def __init__(self) -> None:
        self.finalized = False

    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("Initializing LongRunningMacro", level="INFO")

    def run(self, cmd: Command) -> None:
        for i in range(10):
            cmd.log(f"Running iteration {i}", level="DEBUG")
            cmd.press(Button.A, dur=0.05, wait=0.05)
            time.sleep(0.01)

    def finalize(self, cmd: Command) -> None:
        cmd.log("Finalizing LongRunningMacro", level="INFO")
        self.finalized = True


def test_runtime_normal_flow(tmp_path):
    macro = DummyMacro()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    context = make_fake_execution_context(
        tmp_path,
        macro_id="DummyMacro",
        macro_name="DummyMacro",
        controller=FakeFullCapabilityController(),
    )
    context.frame_source.frame = frame
    runtime = MacroRuntime(Registry({"DummyMacro": macro}))

    result = runtime.run(context)

    assert result.status is RunStatus.SUCCESS
    assert ("press", (Button.A,)) in context.controller.events
    assert ("keyboard", "Hello") in context.controller.events
    assert macro.captured_frame.shape == (720, 1280, 3)
    assert np.all(macro.captured_frame == 0)
    assert any("Initializing DummyMacro" in event.message for event in context.logger.user_events)
    assert any("Finalizing DummyMacro" in event.message for event in context.logger.user_events)


def test_runtime_exception_handling_calls_finalize(tmp_path):
    class ExceptionMacro(MacroBase):
        def initialize(self, cmd: Command, args: dict) -> None:
            cmd.log("init", level="INFO")

        def run(self, cmd: Command) -> None:
            raise RuntimeError("fail!")

        def finalize(self, cmd: Command) -> None:
            cmd.log("final", level="INFO")

    context = make_fake_execution_context(tmp_path, macro_id="ExceptionMacro")
    runtime = MacroRuntime(Registry({"ExceptionMacro": ExceptionMacro()}))

    result = runtime.run(context)

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.message == "fail!"
    assert any("final" in event.message for event in context.logger.user_events)


def test_runtime_cancellation(tmp_path):
    macro = LongRunningMacro()
    context = make_fake_execution_context(tmp_path, macro_id="LongRunningMacro")
    runtime = MacroRuntime(Registry({"LongRunningMacro": macro}))

    def cancel():
        time.sleep(0.05)
        context.cancellation_token.request_cancel(reason="test cancel", source="test")

    thread = threading.Thread(target=cancel)
    thread.start()
    result = runtime.run(context)
    thread.join()

    assert result.status is RunStatus.CANCELLED
    assert macro.finalized is True
    assert context.cancellation_token.stop_requested()


def test_runtime_no_cancellation(tmp_path):
    macro = LongRunningMacro()
    context = make_fake_execution_context(tmp_path, macro_id="LongRunningMacro")
    runtime = MacroRuntime(Registry({"LongRunningMacro": macro}))

    result = runtime.run(context)

    assert result.status is RunStatus.SUCCESS
    assert macro.finalized is True
    assert not context.cancellation_token.stop_requested()
