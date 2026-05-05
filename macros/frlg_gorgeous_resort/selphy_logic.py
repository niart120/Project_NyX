"""アキホおねだり RNG コアロジック

ポケモン決定・アイテム決定の乱数処理を提供する。
仕様: spec/macro/frlg_gorgeous_resort/selphy_rewards.md §4〜§6
"""

from __future__ import annotations

from frlg_initial_seed.lcg32 import LCG32

from .species_data import NUM_SPECIES_CODES

# ============================================================
# 定数
# ============================================================

MAX_RETRY: int = 100

ITEM_TABLE: list[str] = [
    "おおきなしんじゅ",  # 0: 0-4   (5%)
    "しんじゅ",  # 1: 5-9   (5%)
    "ほしのすな",  # 2: 10-14 (5%)
    "ほしのかけら",  # 3: 15-19 (5%)
    "きんのたま",  # 4: 20-24 (5%)
    "ふしぎなアメ",  # 5: 25-29 (5%)
]

LUXURY_BALL: str = "ゴージャスボール"  # 30-99 (70%)


# ============================================================
# ポケモン決定ロジック
# ============================================================


def determine_pokemon(lcg: LCG32, pokedex: set[int]) -> int:
    """アキホが要求するポケモンの内部コードを決定する。

    Args:
        lcg: 現在の乱数状態（破壊的に前進する）
        pokedex: 全国図鑑に登録済みのポケモンの内部コードの集合

    Returns:
        決定されたポケモンの内部コード
    """
    # Phase 1: 乱数による抽選（最大100回）
    for _ in range(MAX_RETRY):
        rand_value = lcg.get_rand()
        species_code = (rand_value % NUM_SPECIES_CODES) + 1
        if species_code in pokedex:
            return species_code

    # Phase 2: フォールバック — 登録済みポケモンを逆順検索
    for code in range(NUM_SPECIES_CODES, 0, -1):
        if code in pokedex:
            return code

    raise RuntimeError("図鑑に登録済みポケモンが1匹もいない")


# ============================================================
# アイテム決定ロジック
# ============================================================


def determine_item(lcg: LCG32) -> str:
    """報酬アイテムを決定する。

    ポケモン決定直後の LCG 状態から呼び出すこと。

    Args:
        lcg: 現在の乱数状態（破壊的に前進する）

    Returns:
        アイテム名
    """
    rand_value = lcg.get_rand()
    value = rand_value % 100

    if value >= 30:
        return LUXURY_BALL

    return ITEM_TABLE[value // 5]


# ============================================================
# 統合: ポケモン + アイテム同時決定
# ============================================================


def determine_reward(lcg: LCG32, pokedex: set[int]) -> tuple[int, str, int]:
    """ポケモンとアイテムを連続で決定する。

    Args:
        lcg: 現在の乱数状態（破壊的に前進する）
        pokedex: 図鑑登録済みポケモンの内部コード集合

    Returns:
        (species_code, item_name, pokemon_consumed)
        pokemon_consumed はポケモン決定で消費した乱数回数
    """
    seed_before = lcg.seed

    species_code = determine_pokemon(lcg, pokedex)

    # ポケモン決定での消費数を算出
    # determine_pokemon 内で advance した回数を逆算
    temp = LCG32(seed_before)
    pokemon_consumed = 0
    while temp.seed != lcg.seed:
        temp.advance()
        pokemon_consumed += 1

    item = determine_item(lcg)

    return species_code, item, pokemon_consumed
