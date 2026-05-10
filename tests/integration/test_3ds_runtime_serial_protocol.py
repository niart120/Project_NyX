from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol, ThreeDSSerialProtocol
from nyxpy.framework.core.io.adapters import SerialControllerOutputPort
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import MacroDefinition
from nyxpy.framework.core.runtime.result import RunStatus
from nyxpy.framework.core.runtime.runtime import MacroRuntime
from tests.support.fake_execution_context import make_fake_execution_context


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
            aliases=(name_or_id,),
            display_name=name_or_id,
            class_name=type(macro).__name__,
            module_name=__name__,
            macro_root=Path(__file__).parent,
            source_path=Path(__file__),
            settings_path=None,
            description="",
            tags=(),
            factory=Factory(macro),
        )


class SerialDevice:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send(self, data: bytes) -> None:
        self.sent.append(data)


class TouchMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        cmd.touch(320, 240, dur=0, wait=0)

    def finalize(self, cmd: Command) -> None:
        pass


class SleepMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        cmd.disable_sleep(True)

    def finalize(self, cmd: Command) -> None:
        pass


class UnsupportedTouchMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        pass

    def run(self, cmd: Command) -> None:
        cmd.touch_down(1, 2)

    def finalize(self, cmd: Command) -> None:
        pass


def _run_macro(tmp_path: Path, macro_id: str, macro: MacroBase, protocol):
    serial = SerialDevice()
    controller = SerialControllerOutputPort(serial, protocol)
    context = make_fake_execution_context(
        tmp_path,
        macro_id=macro_id,
        macro_name=macro_id,
        controller=controller,
    )
    result = MacroRuntime(Registry({macro_id: macro})).run(context)
    return result, serial


def test_3ds_runtime_command_touch_with_fake_serial(tmp_path: Path) -> None:
    result, serial = _run_macro(tmp_path, "touch", TouchMacro(), ThreeDSSerialProtocol())

    assert result.status is RunStatus.SUCCESS
    assert serial.sent == [
        bytes(
            [
                0xA1,
                0x00,
                0x00,
                0xA2,
                0x80,
                0x80,
                0xA4,
                0x00,
                0x00,
                0xB2,
                0x01,
                0x01,
                0x40,
                0xF0,
            ]
        ),
        bytes(
            [
                0xA1,
                0x00,
                0x00,
                0xA2,
                0x80,
                0x80,
                0xA4,
                0x00,
                0x00,
                0xB2,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        ),
    ]


def test_3ds_runtime_command_disable_sleep_with_fake_serial(tmp_path: Path) -> None:
    result, serial = _run_macro(tmp_path, "sleep", SleepMacro(), ThreeDSSerialProtocol())

    assert result.status is RunStatus.SUCCESS
    assert serial.sent == [bytes([0xFC, 0x01])]


def test_non_touch_protocol_runtime_touch_fails_explicitly(tmp_path: Path) -> None:
    result, serial = _run_macro(
        tmp_path, "unsupported", UnsupportedTouchMacro(), CH552SerialProtocol()
    )

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    assert "touch input" in result.error.message
    assert serial.sent == []


def test_3ds_runtime_keeps_basic_button_input_with_touch_support(tmp_path: Path) -> None:
    class ButtonMacro(MacroBase):
        def initialize(self, cmd: Command, args: dict) -> None:
            pass

        def run(self, cmd: Command) -> None:
            cmd.press(Button.A, dur=0, wait=0)

        def finalize(self, cmd: Command) -> None:
            pass

    result, serial = _run_macro(tmp_path, "button", ButtonMacro(), ThreeDSSerialProtocol())

    assert result.status is RunStatus.SUCCESS
    assert serial.sent == [
        bytes(
            [
                0xA1,
                0x10,
                0x00,
                0xA2,
                0x80,
                0x80,
                0xA4,
                0x00,
                0x00,
                0xB2,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        ),
        bytes(
            [
                0xA1,
                0x00,
                0x00,
                0xA2,
                0x80,
                0x80,
                0xA4,
                0x00,
                0x00,
                0xB2,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        ),
    ]
