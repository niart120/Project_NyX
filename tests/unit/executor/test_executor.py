import pytest
import textwrap
from nyxpy.framework.core.macro.executor import MacroExecutor
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.base import MacroBase

# ダミーマクロの実装を書いた Python ファイル用文字列
DUMMY_MACRO_SOURCE = textwrap.dedent("""
    from nyxpy.framework.core.macro.base import MacroBase
    from nyxpy.framework.core.macro.command import Command

    class DummyTestMacro(MacroBase):
        def initialize(self, cmd: Command) -> None:
            pass
        def run(self, cmd: Command) -> None:
            pass
        def finalize(self) -> None:
            pass
""")


@pytest.fixture
def temp_macros_dir(tmp_path, monkeypatch):
    # 一時ディレクトリ内に "macros" ディレクトリを作成
    macros_dir = tmp_path / "macros"
    macros_dir.mkdir()
    # ダミーマクロのファイル作成
    dummy_file = macros_dir / "dummy_macro.py"
    dummy_file.write_text(DUMMY_MACRO_SOURCE)
    # カレントディレクトリとして一時ディレクトリを設定
    monkeypatch.chdir(tmp_path)
    # 一時ディレクトリをsyspathに追加
    monkeypatch.syspath_prepend(tmp_path)
    return macros_dir


def test_load_all_macros(temp_macros_dir):
    executor = MacroExecutor()
    # ダミーマクロ "DummyTestMacro" が macros に読み込まれているかを検証
    assert "DummyTestMacro" in executor.macros
    # 読み込まれたインスタンスが MacroBase のサブクラスであることも確認
    macro_instance = executor.macros["DummyTestMacro"]
    assert isinstance(macro_instance, MacroBase)


def test_set_active_macro(temp_macros_dir, monkeypatch):
    executor = MacroExecutor()
    # 正常ケース: 既存のマクロ名で選択できる
    executor.set_active_macro("DummyTestMacro")
    assert executor.macro.__class__.__name__ == "DummyTestMacro"
    # 異常ケース: 存在しないマクロを指定した場合はValueErrorが発生することを確認
    with pytest.raises(ValueError) as exc_info:
        executor.set_active_macro("NonExistentMacro")
    assert "Macro 'NonExistentMacro' not found" in str(exc_info.value)


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

    def stop(self):
        self.logs.append("stop")

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

    def type(self, key):
        self.logs.append(f"keytype: {key}")


class MockMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("MockMacro: initialize")

    def run(self, cmd: Command) -> None:
        cmd.log("MockMacro: run")

    def finalize(self, cmd: Command) -> None:
        cmd.log("MockMacro: finalize")


class FailingMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
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


@pytest.fixture
def executor_with_dummy():
    # Create an executor and override its macros with our dummy implementations.
    executor = MacroExecutor()
    executor.macros = {"MockMacro": MockMacro(), "FailingMacro": FailingMacro()}
    return executor


def test_macro_executor_lifecycle(executor_with_dummy, mock_command):
    """
    MacroExecutor のライフサイクル (initialize -> run -> finalize) をテスト
    """
    executor_with_dummy.set_active_macro("MockMacro")
    executor_with_dummy.execute(mock_command)

    # ログを確認
    assert mock_command.logs == [
        "MacroExecutor: Loading macro settings...",
        "MacroExecutor: Initializing macro...",
        "MockMacro: initialize",
        "MacroExecutor: Running macro...",
        "MockMacro: run",
        "MacroExecutor: Finalizing macro...",
        "MockMacro: finalize",
    ]


def test_macro_executor_exception_handling(executor_with_dummy, mock_command):
    """
    MacroExecutor が run 中に例外が発生した場合でも finalize が呼び出されることをテスト
    """
    executor_with_dummy.set_active_macro("FailingMacro")
    executor_with_dummy.execute(mock_command)

    # 例外発生時のログを確認
    assert mock_command.logs == [
        "MacroExecutor: Loading macro settings...",
        "MacroExecutor: Initializing macro...",
        "FailingMacro: initialize",
        "MacroExecutor: Running macro...",
        "FailingMacro: run",
        "MacroExecutor: Exception occurred: Intentional Error",
        "MacroExecutor: Finalizing macro...",
        "FailingMacro: finalize",
    ]
