import pytest
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.base import MacroBase

# テスト用のモッククラスを定義
class MockCommand(Command):
    def __init__(self):
        self.logs = []

    def press(self, *keys, dur=0.1, wait=0.1):
        self.logs.append(f"press: {keys}")

    def hold(self, *keys):
        self.logs.append(f"hold: {keys}")

    def release(self, *keys):
        self.logs.append(f"release: {keys}")

    def wait(self, wait):
        self.logs.append(f"wait: {wait}")

    def log(self, *values, sep=" ", end="\n"):
        self.logs.append(" ".join(map(str, values)))

    def capture(self):
        self.logs.append("capture")
        return None
    
    def save_img(self, filename, image):
        self.logs.append(f"save_img: {filename}, image={image}")
    
    def load_img(self, filename, grayscale=False):
        self.logs.append(f"load_img: {filename}, grayscale={grayscale}")
        return None

    def keyboard(self, text):
        self.logs.append(f"keyboard: {text}")

class MockMacro(MacroBase):
    def initialize(self, cmd: Command) -> None:
        cmd.log("MockMacro: initialize")

    def run(self, cmd: Command) -> None:
        cmd.log("MockMacro: run")

    def finalize(self, cmd: Command) -> None:
        cmd.log("MockMacro: finalize")

class FailingMacro(MacroBase):
    def initialize(self, cmd: Command) -> None:
        cmd.log("FailingMacro: initialize")

    def run(self, cmd: Command) -> None:
        cmd.log("FailingMacro: run")
        raise RuntimeError("Intentional Error")
        cmd.log("FailingMacro: run (should not reach here)")

    def finalize(self, cmd: Command) -> None:
        cmd.log("FailingMacro: finalize")

@pytest.fixture
def mock_command():
    return MockCommand()

def test_macro_executor_lifecycle(mock_command):
    """
    MacroExecutor のライフサイクル (initialize -> run -> finalize) をテスト
    """
    executor = MacroExecutor(macro_module="tests.unit.executor.test_executor", macro_class="MockMacro")
    executor.execute(mock_command)

    # ログを確認
    assert mock_command.logs == [
        "MacroExecutor: Initializing macro...",
        "MockMacro: initialize",
        "MacroExecutor: Running macro...",
        "MockMacro: run",
        "MacroExecutor: Finalizing macro...",
        "MockMacro: finalize",
    ]

def test_macro_executor_exception_handling(mock_command):
    """
    MacroExecutor が run 中に例外が発生した場合でも finalize が呼び出されることをテスト
    """
    executor = MacroExecutor(macro_module="tests.unit.executor.test_executor", macro_class="FailingMacro")

    # 例外をキャッチして、ログを確認
    executor.execute(mock_command)

    # 例外発生時のログを確認
    assert mock_command.logs == [
        "MacroExecutor: Initializing macro...",
        "FailingMacro: initialize",
        "MacroExecutor: Running macro...",
        "FailingMacro: run",
        "MacroExecutor: Exception occurred: Intentional Error",
        "MacroExecutor: Finalizing macro...",
        "FailingMacro: finalize",
    ]