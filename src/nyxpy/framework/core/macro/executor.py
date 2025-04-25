import importlib
import inspect
from pathlib import Path

from nyxpy.framework.core.macro.exceptions import MacroStopException
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.utils.helper import load_macro_settings


class MacroExecutor:
    """
    MacroExecutorは、カレントディレクトリ直下のmacrosディレクトリから
    MacroBaseを継承した全てのマクロを読み込み、実行可能マクロのリストとして保持します。

    ・load_all_macros() で利用可能なマクロを読み込みます。
    ・select_macro() によって実行対象のマクロをセットします。
    ・execute() によって選択されたマクロのライフサイクル関数（initialize -> run -> finalize）を呼び出します。
    """

    def __init__(self):
        self.macros: dict[str, MacroBase] = {}
        self.macro: MacroBase = None
        self.load_all_macros()

    def load_all_macros(self) -> None:
        """
        カレントディレクトリ直下の 'macros' フォルダ内の全Pythonモジュールを読み込み、
        MacroBaseを継承したクラスのインスタンスを self.macros に追加します。
        """
        macros_dir = Path.cwd() / "macros"
        if not macros_dir.is_dir():
            # macrosディレクトリがない場合は何もしない
            return
        for file in macros_dir.iterdir():
            if file.suffix == ".py" and file.name != "__init__.py":
                module_name = f"macros.{file.stem}"
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, MacroBase) and obj is not MacroBase:
                            instance = obj()
                            self.macros[obj.__name__] = instance
                except Exception as e:
                    # ログ出力等、例外発生時の処理をここに実装可能
                    log_manager.log(
                        "ERROR",
                        f"Error loading macro:{file.name}, {e}",
                        component="MacroExecutor",
                    )
                    pass

    def select_macro(self, macro_name: str) -> None:
        """
        利用可能マクロの中から、macro_name で指定されたマクロを実行対象として選択する。

        :param macro_name: 実行対象のマクロクラス名
        :raises ValueError: 指定されたマクロ名が見つからなかった場合
        """
        if macro_name in self.macros:
            self.macro = self.macros[macro_name]
        else:
            raise ValueError(
                f"Macro '{macro_name}' not found. Available macros: {list(self.macros.keys())}"
            )

    def execute(self, cmd: Command, exec_args: dict = {}) -> None:
        """
        マクロのライフサイクルに従い、順次処理を実行する。
        例外が発生した場合はログ出力し、最終的に finalize を必ず呼び出す。
        """
        try:
            cmd.log("MacroExecutor: Loading macro settings...")
            file_args = load_macro_settings(self.macro.__class__)
            cmd.log("MacroExecutor: Initializing macro...")
            # 引数をマージする。exec_argsが優先される。
            args = {**file_args, **exec_args}
            self.macro.initialize(cmd, args)
            cmd.log("MacroExecutor: Running macro...")
            self.macro.run(cmd)
        except MacroStopException as e:
            cmd.log("MacroExecutor: Macro execution interrupted:", e)
        except Exception as e:
            cmd.log("MacroExecutor: Exception occurred:", e)
        finally:
            cmd.log("MacroExecutor: Finalizing macro...")
            self.macro.finalize(cmd)
