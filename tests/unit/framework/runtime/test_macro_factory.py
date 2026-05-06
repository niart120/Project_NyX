from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.registry import ClassMacroFactory


class StatefulMacro(MacroBase):
    def __init__(self) -> None:
        self.counter = 0

    def initialize(self, cmd: Command, args: dict) -> None:
        self.counter += 1

    def run(self, cmd: Command) -> None:
        pass

    def finalize(self, cmd: Command) -> None:
        pass


def test_execute_creates_new_instance_each_time() -> None:
    factory = ClassMacroFactory(StatefulMacro)

    first = factory.create()
    second = factory.create()

    assert isinstance(first, StatefulMacro)
    assert isinstance(second, StatefulMacro)
    assert first is not second
    first.counter = 10
    assert second.counter == 0
