import importlib.util
import textwrap
from pathlib import Path

import pytest

from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.executor import MacroExecutor

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
    def __init__(self, notification_handler=None):
        self.logs = []
        self.notification_handler = notification_handler
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
    def notify(self, text, img=None):
        if self.notification_handler:
            self.notification_handler.publish(text, img)


class MockMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("initialize")

    def run(self, cmd: Command) -> None:
        cmd.log("run")

    def finalize(self, cmd: Command) -> None:
        cmd.log("finalize")


class FailingMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("initialize")

    def run(self, cmd: Command) -> None:
        cmd.log("run")
        raise RuntimeError("Intentional Error")
        cmd.log("run (should not reach here)")

    def finalize(self, cmd: Command) -> None:
        cmd.log("finalize")


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
        "Loading macro settings...",
        "Initializing macro...",
        "initialize",
        "Running macro...",
        "run",
        "Finalizing macro...",
        "finalize",
    ]


def test_macro_executor_exception_handling(executor_with_dummy, mock_command):
    """
    MacroExecutor が run 中に例外が発生した場合でも finalize が呼び出されることをテスト
    """
    executor_with_dummy.set_active_macro("FailingMacro")
    
    # 例外発生時は executor 内でハンドリングされるが再スローされる
    # 例外が発生することを確認
    with pytest.raises(RuntimeError):
        executor_with_dummy.execute(mock_command)


    # 例外発生時のログを確認
    assert mock_command.logs == [
        "Loading macro settings...",
        "Initializing macro...",
        "initialize",
        "Running macro...",
        "run",
        "An error occurred during macro execution: Intentional Error",
        "Finalizing macro...",
        "finalize",
    ]


# ---- パッケージ型マクロのリロードテスト ----------------------------------------

PACKAGE_INIT_V1 = textwrap.dedent("""\
    from .impl import PackageMacro
    __all__ = ["PackageMacro"]
""")

PACKAGE_IMPL_V1 = textwrap.dedent("""\
    from nyxpy.framework.core.macro.base import MacroBase
    from nyxpy.framework.core.macro.command import Command

    LABEL = "v1"

    class PackageMacro(MacroBase):
        label = LABEL
        def initialize(self, cmd: Command, args: dict) -> None: pass
        def run(self, cmd: Command) -> None: pass
        def finalize(self, cmd: Command) -> None: pass
""")

PACKAGE_IMPL_V2 = textwrap.dedent("""\
    from nyxpy.framework.core.macro.base import MacroBase
    from nyxpy.framework.core.macro.command import Command

    LABEL = "v2"

    class PackageMacro(MacroBase):
        label = LABEL
        def initialize(self, cmd: Command, args: dict) -> None: pass
        def run(self, cmd: Command) -> None: pass
        def finalize(self, cmd: Command) -> None: pass
""")


@pytest.fixture
def temp_package_macros_dir(tmp_path, monkeypatch):
    """パッケージ型マクロ（サブモジュールあり）用の一時ディレクトリ"""
    macros_dir = tmp_path / "macros"
    pkg_dir = macros_dir / "pkg_macro"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(PACKAGE_INIT_V1)
    (pkg_dir / "impl.py").write_text(PACKAGE_IMPL_V1)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(tmp_path)
    return pkg_dir


def test_package_macro_initial_load(temp_package_macros_dir):
    """パッケージ型マクロが正常にロードされることを確認"""
    executor = MacroExecutor()
    assert "PackageMacro" in executor.macros
    assert executor.macros["PackageMacro"].label == "v1"


def test_package_macro_submodule_reload(temp_package_macros_dir):
    """
    サブモジュールを変更してリロードしたとき、変更が反映されることを確認。
    importlib.reload() のみでは __init__.py だけ再実行されサブモジュールは
    キャッシュ(旧バージョン)が使われてしまう問題を回帰テストする。
    """
    executor = MacroExecutor()
    assert executor.macros["PackageMacro"].label == "v1"

    # サブモジュール impl.py を v2 に書き換える
    (temp_package_macros_dir / "impl.py").write_text(PACKAGE_IMPL_V2)

    # .pyc のタイムスタンプが同一秒になるケースを防ぎ、確実に再コンパイルさせる
    pyc_path = Path(importlib.util.cache_from_source(str(temp_package_macros_dir / "impl.py")))
    if pyc_path.exists():
        pyc_path.unlink()

    executor.reload_macros()

    assert "PackageMacro" in executor.macros, "リロード後もマクロが存在すること"
    assert executor.macros["PackageMacro"].label == "v2", (
        "サブモジュールの変更がリロード後に反映されること"
    )
