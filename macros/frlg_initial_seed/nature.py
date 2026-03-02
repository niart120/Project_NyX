"""性格 (Nature) テーブルと補正倍率

FRLG の性格 ID・日英名・性格補正倍率を管理する。
"""

from __future__ import annotations

# 性格 ID → 英語名
NATURE_NAMES: tuple[str, ...] = (
    "Hardy",    # 0
    "Lonely",   # 1
    "Brave",    # 2
    "Adamant",  # 3
    "Naughty",  # 4
    "Bold",     # 5
    "Docile",   # 6
    "Relaxed",  # 7
    "Impish",   # 8
    "Lax",      # 9
    "Timid",    # 10
    "Hasty",    # 11
    "Serious",  # 12
    "Jolly",    # 13
    "Naive",    # 14
    "Modest",   # 15
    "Mild",     # 16
    "Quiet",    # 17
    "Bashful",  # 18
    "Rash",     # 19
    "Calm",     # 20
    "Gentle",   # 21
    "Sassy",    # 22
    "Careful",  # 23
    "Quirky",   # 24
)

# 英語名 → 性格 ID
NATURE_TO_ID: dict[str, int] = {name: i for i, name in enumerate(NATURE_NAMES)}

# 日本語名 → 英語名 変換テーブル
NATURE_JPN_TO_EN: dict[str, str] = {
    "がんばりや": "Hardy",
    "さみしがり": "Lonely",
    "ゆうかん": "Brave",
    "いじっぱり": "Adamant",
    "やんちゃ": "Naughty",
    "ずぶとい": "Bold",
    "すなお": "Docile",
    "のんき": "Relaxed",
    "わんぱく": "Impish",
    "のうてんき": "Lax",
    "おくびょう": "Timid",
    "せっかち": "Hasty",
    "まじめ": "Serious",
    "ようき": "Jolly",
    "むじゃき": "Naive",
    "ひかえめ": "Modest",
    "おっとり": "Mild",
    "れいせい": "Quiet",
    "てれや": "Bashful",
    "うっかりや": "Rash",
    "おだやか": "Calm",
    "おとなしい": "Gentle",
    "なまいき": "Sassy",
    "しんちょう": "Careful",
    "きまぐれ": "Quirky",
}

# ステータスキー名
_STAT_KEYS = ("Attack", "Defense", "Speed", "SpecialAttack", "SpecialDefense")

# 性格補正テーブル: (上昇ステータス, 下降ステータス)
# 無補正性格は None
_NATURE_MODIFIERS: dict[str, tuple[str, str] | None] = {
    "Hardy": None,
    "Lonely": ("Attack", "Defense"),
    "Brave": ("Attack", "Speed"),
    "Adamant": ("Attack", "SpecialAttack"),
    "Naughty": ("Attack", "SpecialDefense"),
    "Bold": ("Defense", "Attack"),
    "Docile": None,
    "Relaxed": ("Defense", "Speed"),
    "Impish": ("Defense", "SpecialAttack"),
    "Lax": ("Defense", "SpecialDefense"),
    "Timid": ("Speed", "Attack"),
    "Hasty": ("Speed", "Defense"),
    "Serious": None,
    "Jolly": ("Speed", "SpecialAttack"),
    "Naive": ("Speed", "SpecialDefense"),
    "Modest": ("SpecialAttack", "Attack"),
    "Mild": ("SpecialAttack", "Defense"),
    "Quiet": ("SpecialAttack", "Speed"),
    "Bashful": None,
    "Rash": ("SpecialAttack", "SpecialDefense"),
    "Calm": ("SpecialDefense", "Attack"),
    "Gentle": ("SpecialDefense", "Defense"),
    "Sassy": ("SpecialDefense", "Speed"),
    "Careful": ("SpecialDefense", "SpecialAttack"),
    "Quirky": None,
}


def get_nature_multipliers(nature: str) -> dict[str, float]:
    """性格名から各ステータスの補正倍率を返す。

    Args:
        nature: 性格の英語名

    Returns:
        {"Attack": 1.0, "Defense": 1.0, "Speed": 1.0,
         "SpecialAttack": 1.0, "SpecialDefense": 1.0}
        上昇ステータスは 1.1, 下降ステータスは 0.9 になる。
    """
    multipliers = {key: 1.0 for key in _STAT_KEYS}
    modifier = _NATURE_MODIFIERS.get(nature)
    if modifier is not None:
        up_stat, down_stat = modifier
        multipliers[up_stat] = 1.1
        multipliers[down_stat] = 0.9
    return multipliers
