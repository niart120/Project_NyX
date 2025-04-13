import inspect
import tomllib
from pathlib import Path

def get_caller_class_name():
    """呼び出し元のクラス名を取得する関数"""
    frame = inspect.currentframe().f_back  # 呼び出し元のフレーム
    self_var = frame.f_locals.get("self")  # 呼び出し元のローカル変数 `self`
    return type(self_var).__name__ if self_var else None

def load_macro_settings(macro_cls) -> dict:
    """
    指定されたマクロクラスに対応する設定ファイルを読み込み、辞書型のオブジェクトとして返却します。
    設定ファイルは、<current_working_directory>/static/<macro_filename_without_extension>/settings.toml に存在することを想定します。

    :param macro_cls: マクロクラス（例: DummyTestMacro）
    :return: マージされた設定辞書
    """
    macro_file = Path(inspect.getfile(macro_cls))
    macro_name = macro_file.stem  # マクロクラスのファイル名（拡張子なし）
    settings_file = Path.cwd() / "static" / macro_name / "settings.toml"
    file_params = {}
    if settings_file.exists():
        file_params = tomllib.load(settings_file)

    return file_params