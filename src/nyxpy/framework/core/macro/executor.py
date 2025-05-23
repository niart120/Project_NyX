import importlib
import inspect
import sys
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

    ・reload_macros() で利用可能なマクロを読み込みます。
    ・set_active_macro() によって実行対象のマクロをセットします。
    ・execute() によって選択されたマクロのライフサイクル関数（initialize -> run -> finalize）を呼び出します。
    """

    def __init__(self):
        self.macros: dict[str, MacroBase] = {}
        self.macro: MacroBase = None
        # カレントディレクトリをsys.pathに追加する
        if str(Path.cwd()) not in sys.path:
            sys.path.append(str(Path.cwd()))
        self.reload_macros()

    def reload_macros(self) -> None:
        """
        カレントディレクトリ直下の 'macros' フォルダ内の全Pythonモジュールをリロード対応で読み込み、
        MacroBaseを継承したクラスのインスタンスを self.macros に追加します。
        """
        macros_dir = Path.cwd() / "macros"
        self.macros.clear()
        if not macros_dir.is_dir():
            return
        for file in macros_dir.iterdir():
            if file.suffix == ".py" and file.name != "__init__.py":
                module_name = f"macros.{file.stem}"
                try:
                    if module_name in sys.modules:
                        module = importlib.reload(sys.modules[module_name])
                    else:
                        module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, MacroBase) and obj is not MacroBase:
                            instance = obj()
                            self.macros[obj.__name__] = instance
                except Exception as e:
                    log_manager.log(
                        "ERROR",
                        f"Error loading macro:{file.name}, {e}",
                        component="MacroExecutor",
                    )
                    pass

    def set_active_macro(self, macro_name: str) -> None:
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
            cmd.log("Loading macro settings...")
            file_args = load_macro_settings(self.macro.__class__)
            cmd.log("Initializing macro...")
            # 引数をマージする。exec_argsが優先される。
            args = {**file_args, **exec_args}
            self.macro.initialize(cmd, args)
            cmd.log("Running macro...")
            self.macro.run(cmd)
        except MacroStopException as e:
            cmd.log("Macro execution interrupted:", e)
            # マクロの実行が中断された場合は、何もしない。
        except Exception as e:
            cmd.log("An error occurred during macro execution:", e)
            raise e
        finally:
            cmd.log("Finalizing macro...")
            self.macro.finalize(cmd)
