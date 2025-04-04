import importlib
from typing import Type
from .base import MacroBase
from .command import Command

class MacroExecutor:
    """
    MacroExecutorは、指定されたユーザー作成マクロを動的に読み込み、
    ハリウッドの原則に従ってライフサイクル（initialize -> run -> finalize）を実行します。
    """
    def __init__(self, macro_module: str, macro_class: str):
        """
        :param macro_module: ユーザーマクロのモジュールパス（例："macros.sample_macro"）
        :param macro_class: そのモジュール内のマクロ実装クラス名（例："SampleMacro"）
        """
        self.macro = self.load_macro(macro_module, macro_class)

    def load_macro(self, module_name: str, class_name: str) -> MacroBase:
        module = importlib.import_module(module_name)
        macro_class: Type[MacroBase] = getattr(module, class_name)
        instance = macro_class()
        return instance

    def execute(self, cmd: Command) -> None:
        """
        マクロのライフサイクルに従い、順次処理を実行する。
        例外が発生した場合はログ出力し、最終的に finalize を必ず呼び出す。
        """
        try:
            cmd.log("MacroExecutor: Initializing macro...")
            self.macro.initialize(cmd)
            cmd.log("MacroExecutor: Running macro...")
            self.macro.run(cmd)
        except Exception as e:
            cmd.log("MacroExecutor: Exception occurred:", e)
        finally:
            cmd.log("MacroExecutor: Finalizing macro...")
            self.macro.finalize(cmd)
