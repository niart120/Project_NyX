from __future__ import annotations

import threading
import time
from datetime import datetime

import pytest

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.exceptions import (
    ErrorKind,
    FrameworkError,
    MacroCancelled,
    MacroStopException,
)
from nyxpy.framework.core.runtime import MacroRunner, RunContext, RunResult, RunStatus
from nyxpy.framework.core.settings.schema import SettingField, SettingsSchema
from nyxpy.framework.core.utils.cancellation import CancellationToken, cancellation_aware_wait


class RecordingCommand(Command):
    def __init__(self, token: CancellationToken | None = None) -> None:
        self.events: list[str] = []
        self.ct = token or CancellationToken()

    def press(self, *keys, dur=0.1, wait=0.1) -> None:
        self.events.append("press")

    def hold(self, *keys) -> None:
        self.events.append("hold")

    def release(self, *keys) -> None:
        self.events.append("release")

    def wait(self, wait: float) -> None:
        cancellation_aware_wait(wait, self.ct)
        self.ct.throw_if_requested()

    def stop(self) -> None:
        self.ct.request_cancel(reason="stop requested", source="macro")

    def log(self, *values, sep: str = " ", end: str = "\n", level: str = "DEBUG") -> None:
        self.events.append(sep.join(map(str, values)) + end.rstrip("\n"))

    def capture(self, crop_region=None, grayscale: bool = False):
        return None

    def save_img(self, filename, image) -> None:
        self.events.append(f"save:{filename}")

    def load_img(self, filename, grayscale: bool = False):
        return None

    def keyboard(self, text: str) -> None:
        self.events.append(f"keyboard:{text}")

    def type(self, key) -> None:
        self.events.append(f"type:{key}")

    def notify(self, text: str, img=None) -> None:
        self.events.append(f"notify:{text}")


def _run_context(token: CancellationToken | None = None) -> RunContext:
    return RunContext(
        run_id="run-1",
        macro_id="macro-1",
        macro_name="MacroOne",
        started_at=datetime.now(),
        cancellation_token=token or CancellationToken(),
        logger=None,
    )


class OrderedMacro(MacroBase):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def initialize(self, cmd: Command, args: dict) -> None:
        self.events.append(f"initialize:{args['value']}")

    def run(self, cmd: Command) -> None:
        self.events.append("run")

    def finalize(self, cmd: Command) -> None:
        self.events.append("finalize")


class ArgsSchemaMacro(OrderedMacro):
    args_schema = SettingsSchema(
        fields={
            "count": SettingField("count", int, 1),
            "label": SettingField("label", str, "default"),
        },
        preserve_unknown=False,
    )

    def initialize(self, cmd: Command, args: dict) -> None:
        self.events.append("initialize")
        self.args = args


def test_runner_calls_lifecycle_in_order() -> None:
    events: list[str] = []
    result = MacroRunner().run(
        OrderedMacro(events),
        RecordingCommand(),
        {"value": "ok"},
        _run_context(),
    )

    assert events == ["initialize:ok", "run", "finalize"]
    assert result.status is RunStatus.SUCCESS
    assert result.error is None
    assert result.ok


def test_runner_validates_macro_args_schema_and_applies_defaults() -> None:
    events: list[str] = []
    macro = ArgsSchemaMacro(events)

    result = MacroRunner().run(macro, RecordingCommand(), {"count": 3}, _run_context())

    assert result.status is RunStatus.SUCCESS
    assert macro.args == {"count": 3, "label": "default"}


def test_runner_returns_configuration_error_for_invalid_macro_args() -> None:
    events: list[str] = []
    macro = ArgsSchemaMacro(events)

    result = MacroRunner().run(macro, RecordingCommand(), {"count": "many"}, _run_context())

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "NYX_MACRO_ARGS_INVALID"
    assert result.error.kind is ErrorKind.CONFIGURATION
    assert events == ["finalize"]


class ErrorMacro(MacroBase):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def initialize(self, cmd: Command, args: dict) -> None:
        self.events.append("initialize")

    def run(self, cmd: Command) -> None:
        self.events.append("run")
        raise RuntimeError("boom")

    def finalize(self, cmd: Command) -> None:
        self.events.append("finalize")


def test_runner_calls_finalize_on_error() -> None:
    events: list[str] = []
    result = MacroRunner().run(ErrorMacro(events), RecordingCommand(), {}, _run_context())

    assert events == ["initialize", "run", "finalize"]
    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "NYX_MACRO_FAILED"
    assert result.error.exception_type == "RuntimeError"


class StopMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        raise MacroStopException("legacy stop")

    def finalize(self, cmd: Command) -> None:
        self.finalized = True


def test_runner_converts_macro_stop_to_cancelled() -> None:
    macro = StopMacro()

    result = MacroRunner().run(macro, RecordingCommand(), {}, _run_context())

    assert result.status is RunStatus.CANCELLED
    assert result.error is not None
    assert result.error.kind is ErrorKind.CANCELLED
    assert result.error.code == "NYX_MACRO_CANCELLED"
    assert macro.finalized is True


def test_macro_cancelled_is_macro_stop_exception_compatible() -> None:
    with pytest.raises(MacroStopException):
        raise MacroCancelled("cancelled")


def test_macro_stop_exception_constructor_keeps_legacy_calls() -> None:
    empty = MacroStopException()
    with_message = MacroStopException("stop")

    assert str(empty) == ""
    assert str(with_message) == "stop"
    assert with_message.kind is ErrorKind.CANCELLED
    assert with_message.code == "NYX_MACRO_CANCELLED"
    assert with_message.component == "MacroStopException"


def test_framework_error_contains_kind_code_component() -> None:
    error = FrameworkError(
        "broken",
        kind=ErrorKind.INTERNAL,
        code="NYX_INTERNAL",
        component="test",
        details={"key": "value"},
    )

    assert error.kind is ErrorKind.INTERNAL
    assert error.code == "NYX_INTERNAL"
    assert error.component == "test"
    assert error.details == {"key": "value"}


def test_cancellation_token_request_cancel_is_idempotent() -> None:
    token = CancellationToken()

    token.request_cancel(reason="first", source="gui")
    first_requested_at = token.requested_at()
    token.request_cancel(reason="second", source="cli")

    assert token.stop_requested()
    assert token.reason() == "first"
    assert token.source() == "gui"
    assert token.requested_at() == first_requested_at

    token.clear()
    assert not token.stop_requested()
    assert token.reason() is None
    assert token.source() is None
    assert token.requested_at() is None


def test_command_wait_returns_immediately_on_cancel() -> None:
    token = CancellationToken()

    def cancel() -> None:
        time.sleep(0.05)
        token.request_cancel(reason="test", source="unit")

    thread = threading.Thread(target=cancel)
    started = time.perf_counter()
    thread.start()
    with pytest.raises(MacroCancelled):
        RecordingCommand(token).wait(5.0)
    elapsed = time.perf_counter() - started
    thread.join()

    assert elapsed < 0.15


class CmdOnlyFinalizeMacro(MacroBase):
    def __init__(self) -> None:
        self.finalized = 0

    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        pass

    def finalize(self, cmd: Command) -> None:
        self.finalized += 1


def test_finalize_cmd_only_remains_supported() -> None:
    macro = CmdOnlyFinalizeMacro()

    result = MacroRunner().run(macro, RecordingCommand(), {}, _run_context())

    assert result.status is RunStatus.SUCCESS
    assert macro.finalized == 1


class OutcomeFinalizeMacro(MacroBase):
    def __init__(self) -> None:
        self.outcome: RunResult | None = None
        self.finalized = 0

    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        pass

    def finalize(self, cmd: Command) -> None:
        self.finalized += 1

    def finalize_with_outcome(self, cmd: Command, outcome: RunResult) -> None:
        self.outcome = outcome


def test_finalize_receives_outcome_when_supported() -> None:
    macro = OutcomeFinalizeMacro()

    result = MacroRunner().run(macro, RecordingCommand(), {}, _run_context())

    assert result.status is RunStatus.SUCCESS
    assert macro.outcome is not None
    assert macro.outcome.status is RunStatus.SUCCESS
    assert macro.finalized == 0


class FinalizeFailsAfterErrorMacro(ErrorMacro):
    def finalize(self, cmd: Command) -> None:
        self.events.append("finalize")
        raise RuntimeError("finalize boom")


def test_finalize_error_is_added_without_losing_original_error() -> None:
    events: list[str] = []

    result = MacroRunner().run(
        FinalizeFailsAfterErrorMacro(events),
        RecordingCommand(),
        {},
        _run_context(),
    )

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert result.error.message == "boom"
    assert result.error.details["finalize_error"]["message"] == "finalize boom"
