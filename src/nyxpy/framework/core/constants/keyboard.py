"""
キーボード関連の定数

このモジュールはキーボード操作に関する定数を定義します。
"""

from enum import IntEnum


# キーボード操作の種類を定義する列挙型
class KeyboardOp(IntEnum):
    """
    キーボード操作の種類を表す列挙型
    """

    PRESS = 1
    RELEASE = 2
    SPECIAL_PRESS = 3
    SPECIAL_RELEASE = 4
    ALL_RELEASE = 5
    PUSH = 6  # UNUSED
    SPECIAL_PUSH = 7  # UNUSED


# キーボードの通常キーのキーコードを定義
class KeyCode(int):
    """
    キーボードの通常キーのキーコードを表すクラス
    """

    def __new__(cls, char: str = None):
        # 空文字又は Noneの時は0x00として扱う
        if char is None or len(char) == 0:
            char = chr(0x00)
        elif len(char) > 1:
            raise ValueError(f"KeyCode must be a single character, got '{char}'")

        ascii_code = ord(char)
        if ascii_code > 127:
            raise ValueError(f"Character '{char}' is not in ASCII range")

        instance = super().__new__(cls, ascii_code)
        instance.char = char
        return instance

    def __str__(self):
        return self.char


# キーボードの特殊キーのキーコードを定義
class SpecialKeyCode(IntEnum):
    """
    キーボードの特殊キーのキーコードを定義します。
    特殊キー（ENTER, ESCAPE, BACKSPACE, TAB, SPACEなど）を定義します。
    また、日本語キーボード固有の半角・全角なども含みます
    """

    # 特殊キー
    ENTER = 0x28
    ESCAPE = 0x29
    BACKSPACE = 0x2A
    TAB = 0x2B
    SPACE = 0x22

    # JPキーボード固有
    HANZEN = 0x35
    BLACKSLASH = 0x87
    HIRAGANA = 0x88
    YEN = 0x89
    HENKAN = 0x8A
    MUHENKAN = 0x8B

    # 方向キー
    ARROW_RIGHT = 0x4F
    ARROW_LEFT = 0x50
    ARROW_DOWN = 0x51
    ARROW_UP = 0x52

    def __str__(self):
        return self.value
