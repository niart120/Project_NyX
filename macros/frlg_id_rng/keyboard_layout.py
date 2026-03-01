"""
キーボードレイアウト定義

ゲーム内ソフトキーボードの文字配列をデータとして管理し、
名前入力ロジック (enter_name) から参照する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class KeyboardLayout:
    """1 つのキーボードモードのレイアウト

    grid の各文字列が行を表し、文字の index が列座標に対応する。
    """

    grid: tuple[str, ...]


@dataclass(frozen=True)
class RegionKeyboard:
    """リージョンごとのキーボード定義"""

    modes: tuple[KeyboardLayout, ...]
    """3 モード分 (循環切替)"""

    dakuten_map: dict[str, str] | None = None
    """濁点: 変換後文字 → ベース文字"""

    handakuten_map: dict[str, str] | None = None
    """半濁点: 変換後文字 → ベース文字"""

    dakuten_pos: tuple[int, int] | None = None
    """濁点キー座標 (x, y)"""

    handakuten_pos: tuple[int, int] | None = None
    """半濁点キー座標 (x, y)"""

    compute_offset: Callable[[str, int], int] | None = None
    """文字 + 入力済み文字数 → 追加オフセットを返す関数"""


# ============================================================
# 共通ヘルパー
# ============================================================


def _no_offset(_char: str, _count: int) -> int:
    return 0


# ============================================================
# JPN キーボード
# ============================================================

# 空白 = "　" (全角スペースをパディングとして使用)
_JPN_HIRAGANA = KeyboardLayout(
    grid=(
        "あいうえお　なにぬねの　やゆよ！？🅂",
        "かきくけこ　はひふへほ　わをん　濁半",
        "さしすせそ　まみむめも　ゃゅょっー　",
        "たちつてと　らりるれろ　ぁぃぅぇぉ　",
    )
)

_JPN_KATAKANA = KeyboardLayout(
    grid=(
        "アイウエオ　ナニヌネノ　ヤユヨ！？🅂",
        "カキクケコ　ハヒフヘホ　ワヲン　濁半",
        "サシスセソ　マミムメモ　ャュョッー　",
        "タチツテト　ラリルレロ　ァィゥェォ　",
    )
)

_JPN_ALNUM = KeyboardLayout(
    grid=(
        "ABCDEFGHIJKLMNOPQRS",
        "TUVWXYZ　0123456789",
        "abcdefghijklmnopqrs",
        "tuvwxyz　。・…『』「」/♂♀",
    )
)

_JPN_DAKUTEN_MAP: dict[str, str] = {
    # ひらがな濁点
    "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
    "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
    "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
    "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
    # カタカナ濁点
    "ガ": "カ", "ギ": "キ", "グ": "ク", "ゲ": "ケ", "ゴ": "コ",
    "ザ": "サ", "ジ": "シ", "ズ": "ス", "ゼ": "セ", "ゾ": "ソ",
    "ダ": "タ", "ヂ": "チ", "ヅ": "ツ", "デ": "テ", "ド": "ト",
    "バ": "ハ", "ビ": "ヒ", "ブ": "フ", "ベ": "ヘ", "ボ": "ホ",
    "ヴ": "ウ",
}

_JPN_HANDAKUTEN_MAP: dict[str, str] = {
    "ぱ": "は", "ぴ": "ひ", "ぷ": "ふ", "ぺ": "へ", "ぽ": "ほ",
    "パ": "ハ", "ピ": "ヒ", "プ": "フ", "ペ": "ヘ", "ポ": "ホ",
}

JPN_KEYBOARD = RegionKeyboard(
    modes=(_JPN_HIRAGANA, _JPN_KATAKANA, _JPN_ALNUM),
    dakuten_map=_JPN_DAKUTEN_MAP,
    handakuten_map=_JPN_HANDAKUTEN_MAP,
    dakuten_pos=(16, 1),   # 「濁」の位置
    handakuten_pos=(17, 1),  # 「半」の位置
    compute_offset=_no_offset,
)


# ============================================================
# ENG / ESP / ITA キーボード (共通レイアウト)
# ============================================================

# 元スクリプトの ENG 配列:
#   行0: A B C D E F [殻] .
#   行1: G H I J K L [殻] ,
#   行2: M N O P Q R S [唐]
#   行3: T U V W X Y Z [唐]
# 「殻」「唐」はオフセット生成用のプレースホルダ

_ENG_UPPER = KeyboardLayout(
    grid=(
        "ABCDEF殻.",
        "GHIJKL殻,",
        "MNOPQRS唐",
        "TUVWXYZ唐",
    )
)

_ENG_LOWER = KeyboardLayout(
    grid=(
        "abcdef殻.",
        "ghijkl殻,",
        "mnopqrs唐",
        "tuvwxyz唐",
    )
)

_ENG_NUMSYM = KeyboardLayout(
    grid=(
        "01234",
        "56789",
        "!?♂♀/-",
        "…""''",
    )
)


def _eng_offset(char: str, char_count: int) -> int:
    """ENG/ESP/ITA 系のレイアウト固有オフセット

    - S, Z, s, z の行末文字 → offset=1
    - '.', ',' の行末記号 → offset=2
    - 5文字目入力後は追加 offset なし
    """
    if char in ("S", "Z", "s", "z"):
        return 1
    if char in (".", ","):
        return 2
    return 0


ENG_KEYBOARD = RegionKeyboard(
    modes=(_ENG_UPPER, _ENG_LOWER, _ENG_NUMSYM),
    compute_offset=_eng_offset,
)


# ============================================================
# FRA キーボード
# ============================================================

_FRA_UPPER = KeyboardLayout(
    grid=(
        "ABCDEFGH.×",
        "IJKLMNOP,×",
        "QRSTUVWX辛×",
        "YZ  - 殻唐辛×",
    )
)

_FRA_LOWER = KeyboardLayout(
    grid=(
        "abcdefgh.×",
        "ijklmnop,×",
        "qrstuvwx辛×",
        "yz  - 殻唐辛×",
    )
)

_FRA_NUMSYM = KeyboardLayout(
    grid=(
        "01234",
        "56789",
        "!?♂♀/-",
        "…""''",
    )
)


def _fra_offset(char: str, char_count: int) -> int:
    """FRA レイアウト固有オフセット

    G/O/W 系 → 1, H/P/X 系 → 2, '.'/','/'辛' → 3
    """
    if char in ("G", "O", "W", "g", "o", "w"):
        return 1
    if char in ("H", "P", "X", "h", "p", "x"):
        return 2
    if char in (".", ","):
        return 3
    return 0


FRA_KEYBOARD = RegionKeyboard(
    modes=(_FRA_UPPER, _FRA_LOWER, _FRA_NUMSYM),
    compute_offset=_fra_offset,
)


# ============================================================
# NOE キーボード
# ============================================================

_NOE_UPPER = KeyboardLayout(
    grid=(
        "ABCDEFGH.×",
        "IJKLMNOP,×",
        "QRSTUVWX辛×",
        "YZÄÖÜ殻唐辛×",
    )
)

_NOE_LOWER = KeyboardLayout(
    grid=(
        "abcdefgh.×",
        "ijklmnop,×",
        "qrstuvwx辛×",
        "yzäöü殻唐辛×",
    )
)

_NOE_NUMSYM = KeyboardLayout(
    grid=(
        "01234",
        "56789",
        "!?♂♀/-",
        "…""''",
    )
)


def _noe_offset(char: str, char_count: int) -> int:
    """NOE レイアウト固有オフセット (FRA と同構造)"""
    return _fra_offset(char, char_count)


NOE_KEYBOARD = RegionKeyboard(
    modes=(_NOE_UPPER, _NOE_LOWER, _NOE_NUMSYM),
    compute_offset=_noe_offset,
)


# ============================================================
# リージョン → キーボード マッピング
# ============================================================

REGION_KEYBOARDS: dict[str, RegionKeyboard] = {
    "JPN": JPN_KEYBOARD,
    "ENG": ENG_KEYBOARD,
    "ESP": ENG_KEYBOARD,
    "ITA": ENG_KEYBOARD,
    "FRA": FRA_KEYBOARD,
    "NOE": NOE_KEYBOARD,
}


# ============================================================
# ユーティリティ: 文字検索
# ============================================================


def find_char_in_keyboard(
    keyboard: RegionKeyboard,
    char: str,
) -> tuple[int, int, int] | None:
    """キーボード全モードから文字を検索し (mode_index, x, y) を返す。

    見つからなければ ``None``。
    """
    for mode_idx, layout in enumerate(keyboard.modes):
        for y, row in enumerate(layout.grid):
            x = row.find(char)
            if x >= 0:
                return mode_idx, x, y
    return None
