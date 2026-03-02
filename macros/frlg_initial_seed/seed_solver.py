"""初期Seed逆算ロジック (Seed Solver)

画像認識で取得した性格・実数値から、16bit 初期Seed を逆算する。
"""

from __future__ import annotations

from .lcg32 import LCG32
from .nature import NATURE_NAMES, NATURE_TO_ID, get_nature_multipliers
from .pokemon_gen import Pokemon, generate_pokemon


def _matches(
    pokemon: Pokemon,
    expected_nature_id: int | None,
    nature_mults: dict[int, dict[str, float]],
    observed_stats: tuple[int, int, int, int, int, int],
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
) -> bool:
    """生成された個体の実数値が観測値と一致するか判定する。

    expected_nature_id が None の場合、性格フィルタをスキップし
    個体自身の性格補正でステータスのみ照合する。
    """
    # 1. 性格の早期棄却（性格が既知の場合のみ）
    if expected_nature_id is not None and pokemon.nature_id != expected_nature_id:
        return False

    # 2. IV → 実数値を順方向計算し、観測値と直接比較
    mult = nature_mults[pokemon.nature_id]
    calc_stats = pokemon.calc_stats(base_stats, level, mult)
    return calc_stats == observed_stats


def _build_nature_mults(
    nature: str | None,
) -> tuple[int | None, dict[int, dict[str, float]]]:
    """性格補正テーブルを構築する。

    nature が指定されている場合はその 1 性格分のみ、
    None の場合は全 25 性格分を構築する。
    """
    if nature is not None:
        nid = NATURE_TO_ID[nature]
        return nid, {nid: get_nature_multipliers(nature)}

    mults: dict[int, dict[str, float]] = {}
    for name in NATURE_NAMES:
        mults[NATURE_TO_ID[name]] = get_nature_multipliers(name)
    return None, mults


def solve_initial_seed(
    nature: str | None,
    observed_stats: tuple[int, int, int, int, int, int],
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
    min_advance: int,
    max_advance: int,
) -> tuple[str, int | None]:
    """初期Seed を逆算する。

    Args:
        nature: 画像認識で取得した性格名 (英語名)。
                None の場合はステータスのみで照合する。
        observed_stats: 画像認識で取得した実数値 (HP, Atk, Def, SpA, SpD, Spe)
        base_stats: 対象ポケモンの種族値 (HP, Atk, Def, SpA, SpD, Spe)
        level: 対象ポケモンのレベル
        min_advance: 探索フレーム下限（閉区間）
        max_advance: 探索フレーム上限（閉区間）

    Returns:
        (seed, advance) のタプル。
        - 一意に特定できた場合: ("XXXX", advance)
        - 候補が見つからない:   ("False", None)
        - 候補が2つ以上:       ("MultipleSeeds", None)
    """
    nature_id, nature_mults = _build_nature_mults(nature)

    result_count = 0
    result_seed = ""
    result_advance: int | None = None

    for initial_seed in range(0x10000):  # 0x0000 .. 0xFFFF
        lcg = LCG32(initial_seed)
        lcg.advance(min_advance)

        for adv in range(min_advance, max_advance + 1):
            pokemon = generate_pokemon(lcg)

            if _matches(
                pokemon,
                nature_id,
                nature_mults,
                observed_stats,
                base_stats,
                level,
            ):
                result_count += 1
                result_seed = f"{initial_seed:04X}"
                result_advance = adv

            # generate_pokemon で 4step 進んだので 3step 戻る → 差分 +1
            lcg.back(3)

    if result_count == 0:
        return ("False", None)
    elif result_count == 1:
        return (result_seed, result_advance)
    else:
        return ("MultipleSeeds", None)
