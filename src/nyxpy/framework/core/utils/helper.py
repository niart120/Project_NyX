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

def parse_define_args(defines: list[str]) -> dict:
    """ 
    コマンドライン引数で渡された定義を解析して辞書に変換する関数
    key=value 形式の文字列を受け取り、tomlパーサに従う形で辞書に変換する。
    例えば、以下のような引数が渡された場合:

    `-D key1=value1 -D key2.key3=value2`

    これを辞書に変換すると:
    ```
    {
        "key1": "value1",
        "key2": {
            "key3": "value2"
        }
    }
    ```
    となる。

    """
    
    toml_str = "\n".join(defines)  # 引数を改行で結合
    toml_str = toml_str.replace("=", " = ")  # 等号の前後にスペースを追加
    exec_args = tomllib.loads(toml_str)  # toml形式で解析
    
    # 変換された辞書を返す
    return exec_args

def validate_keyboard_text(text: str, allow_special: bool = True) -> str:
    """
    指定されたテキストがキーボード入力として有効かどうかを検証します。
    有効な文字は、ASCIIの印刷可能な文字（0x20から0x7F）です。
    特殊キーコードを許可する場合は、allow_specialをTrueに設定します。

    :param text: 検証するテキスト
    :param allow_special: 特殊キーコードを許可するかどうかのフラグ
    :return: 検証されたテキスト
    :raises ValueError: 無効な文字が含まれている場合
    """

    # 入力が空でないことを確認
    if not text:
        raise ValueError("Input text is empty.")

    # ASCIIの印刷可能な文字を定義
    valid_ascii = set(chr(i) for i in range(0x20, 0x7F))  # printable ASCII
    if allow_special:
        # 例: 特殊キーコードを追加
        valid_ascii.update(['\n', '\t'])  # 必要に応じて

    for c in text:
        if c not in valid_ascii:
            raise ValueError(f"Unsupported character for keyboard input: {repr(c)}")

    return text

def extract_macro_tags(macros: dict[str, any]) -> list[str]:
    """
    マクロ辞書からユニークなタグリストを抽出します。GUIのタグフィルタ用に利用。
    """
    tags = set()
    for m in macros.values():
        tags.update(getattr(m, 'tags', []))
    return sorted(tags)