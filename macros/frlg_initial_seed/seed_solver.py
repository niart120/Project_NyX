"""初期Seed逆算ロジック (Seed Solver)

画像認識で取得した性格・実数値から、16bit 初期Seed を逆算する。

内部実装は numpy ベクトル化により、65,536 通りの初期Seed を一括並列計算する。
"""

from __future__ import annotations

import numpy as np

from .lcg32 import LCG32
from .nature import NATURE_NAMES, NATURE_TO_ID, get_nature_multipliers

# ---- numpy 用 LCG 定数 (uint64 で演算し下位 32bit をマスク) ----
_A64 = np.uint64(LCG32.A)
_C64 = np.uint64(LCG32.C)
_MASK64 = np.uint64(LCG32.MASK)


def _calc_stat_vec(
    base: int, ivs: np.ndarray, level: int, mult: float
) -> np.ndarray:
    """HP 以外のステータス実数値をベクトル計算する。

    int(((2 * base + iv) * level // 100 + 5) * mult) を numpy 配列で一括算出。
    """
    raw = (2 * base + ivs.astype(np.int32)) * level // 100 + 5
    return (raw * mult).astype(np.int32)


def _build_nature_mults(
    nature: str | None,
) -> tuple[int | None, dict[int, dict[str, float]]]:
    """性格補正テーブルを構築する。"""
    if nature is not None:
        nid = NATURE_TO_ID[nature]
        return nid, {nid: get_nature_multipliers(nature)}

    mults: dict[int, dict[str, float]] = {}
    for i, name in enumerate(NATURE_NAMES):
        mults[i] = get_nature_multipliers(name)
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

    b_hp, b_atk, b_def, b_spa, b_spd, b_spe = base_stats
    o_hp, o_atk, o_def, o_spa, o_spd, o_spe = observed_stats

    # 全 65,536 通りの初期Seed
    seeds = np.arange(0x10000, dtype=np.uint64)

    # O(log n) ジャンプで min_advance 位置まで一気に進める
    an, cn = LCG32.jump_constants(min_advance)
    states = (np.uint64(an) * seeds + np.uint64(cn)) & _MASK64

    result_count = 0
    result_seed = ""
    result_advance: int | None = None

    for adv in range(min_advance, max_advance + 1):
        # ---- LCG 4step 一括計算 (get_rand ×4) ----
        s1 = (_A64 * states + _C64) & _MASK64
        lid = ((s1 >> np.uint64(16)) & np.uint64(0xFFFF)).astype(np.uint32)

        s2 = (_A64 * s1 + _C64) & _MASK64
        hid = ((s2 >> np.uint64(16)) & np.uint64(0xFFFF)).astype(np.uint32)

        s3 = (_A64 * s2 + _C64) & _MASK64
        hab = ((s3 >> np.uint64(16)) & np.uint64(0xFFFF)).astype(np.uint32)

        s4 = (_A64 * s3 + _C64) & _MASK64
        scd = ((s4 >> np.uint64(16)) & np.uint64(0xFFFF)).astype(np.uint32)

        # ---- PID → 性格フィルタ (96% を棄却) ----
        pid = lid | (hid << np.uint32(16))
        nature_ids = pid % np.uint32(25)

        if nature_id is not None:
            # 性格が既知: 1 性格分のみ照合
            mask = nature_ids == np.uint32(nature_id)
            if not mask.any():
                states = s1
                continue
            natures_to_check = [(nature_id, mask)]
        else:
            # 性格不明: 全 25 性格を順にチェック
            natures_to_check = []
            for nid in range(25):
                m = nature_ids == np.uint32(nid)
                if m.any():
                    natures_to_check.append((nid, m))

        for nid, mask in natures_to_check:
            mult = nature_mults[nid]

            # ---- IV 抽出 ----
            m_hab = hab[mask]
            m_scd = scd[mask]
            iv_hp = m_hab & np.uint32(0x1F)
            iv_atk = (m_hab >> np.uint32(5)) & np.uint32(0x1F)
            iv_def = (m_hab >> np.uint32(10)) & np.uint32(0x1F)
            iv_spe = m_scd & np.uint32(0x1F)
            iv_spa = (m_scd >> np.uint32(5)) & np.uint32(0x1F)
            iv_spd = (m_scd >> np.uint32(10)) & np.uint32(0x1F)

            # ---- 段階的ステータス照合 (早期棄却) ----
            # HP
            hp = (
                (2 * b_hp + iv_hp.astype(np.int32)) * level
            ) // 100 + level + 10
            ok = hp == o_hp
            if not ok.any():
                continue

            # Atk
            atk = _calc_stat_vec(b_atk, iv_atk[ok], level, mult["Attack"])
            ok2 = atk == o_atk
            if not ok2.any():
                continue

            # Def
            def_ = _calc_stat_vec(b_def, iv_def[ok][ok2], level, mult["Defense"])
            ok3 = def_ == o_def
            if not ok3.any():
                continue

            # SpA
            spa = _calc_stat_vec(
                b_spa, iv_spa[ok][ok2][ok3], level, mult["SpecialAttack"]
            )
            ok4 = spa == o_spa
            if not ok4.any():
                continue

            # SpD
            spd = _calc_stat_vec(
                b_spd, iv_spd[ok][ok2][ok3][ok4], level, mult["SpecialDefense"]
            )
            ok5 = spd == o_spd
            if not ok5.any():
                continue

            # Spe
            spe = _calc_stat_vec(
                b_spe, iv_spe[ok][ok2][ok3][ok4][ok5], level, mult["Speed"]
            )
            ok6 = spe == o_spe
            if not ok6.any():
                continue

            # ---- ヒットした初期Seed を復元 ----
            original_idx = np.where(mask)[0]
            hit_idx = original_idx[ok][ok2][ok3][ok4][ok5][ok6]
            for idx in hit_idx:
                result_count += 1
                result_seed = f"{int(idx):04X}"
                result_advance = adv

        # net +1 step: states を 1step 進める
        states = s1

    if result_count == 0:
        return ("False", None)
    elif result_count == 1:
        return (result_seed, result_advance)
    else:
        return ("MultipleSeeds", None)
