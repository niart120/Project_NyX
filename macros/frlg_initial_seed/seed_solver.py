"""初期Seed逆算ロジック (Seed Solver)

画像認識で取得した実数値から、16bit 初期Seed を逆算する。

PID から導出される性格の補正を考慮した実数値照合で候補を絞り込む。
内部実装は numpy ベクトル化により、65,536 通りの初期Seed を一括並列計算する。
"""

from __future__ import annotations

import numpy as np

from .lcg32 import LCG32
from .nature import NATURE_NAMES, get_nature_multipliers

# ---- numpy 用 LCG 定数 (uint64 で演算し下位 32bit をマスク) ----
_A64 = np.uint64(LCG32.A)
_C64 = np.uint64(LCG32.C)
_MASK64 = np.uint64(LCG32.MASK)


def _build_nature_mult_arrays() -> dict[str, np.ndarray]:
    """全25性格の補正値を stat キー別の numpy 配列として構築する。

    Returns:
        {"Attack": float64[25], "Defense": ..., ...}
        nature_id でインデクシングして各 seed の補正値を一括取得できる。
    """
    keys = ("Attack", "Defense", "SpecialAttack", "SpecialDefense", "Speed")
    arrays: dict[str, np.ndarray] = {k: np.empty(25, dtype=np.float64) for k in keys}
    for i, name in enumerate(NATURE_NAMES):
        mult = get_nature_multipliers(name)
        for k in keys:
            arrays[k][i] = mult[k]
    return arrays


def solve_initial_seed(
    observed_stats: tuple[int, int, int, int, int, int],
    base_stats: tuple[int, int, int, int, int, int],
    level: int,
    min_advance: int,
    max_advance: int,
) -> tuple[str, int | None]:
    """初期Seed を逆算する。

    PID から導出される性格補正を考慮し、実数値のみで照合する。

    Args:
        observed_stats: 画像認識で取得した実数値 (HP, Atk, Def, SpA, SpD, Spe)
        base_stats: 対象ポケモンの種族値 (HP, Atk, Def, SpA, SpD, Spe)
        level: 対象ポケモンのレベル
        min_advance: 探索フレーム下限（閉区間）
        max_advance: 探索フレーム上限（閉区間）

    Returns:
        (seed, advance) のタプル。
        - 一意に特定できた場合: ("XXXX", advance)
        - 候補が見つからない:   ("False", None)
        - 候補が2つ以上:       ("MULT", None)
    """
    nature_mult_arrays = _build_nature_mult_arrays()

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

        # ---- PID → 性格導出 ----
        pid = lid | (hid << np.uint32(16))
        nature_ids = (pid % np.uint32(25)).astype(np.intp)

        # ---- IV 抽出 ----
        iv_hp  = hab & np.uint32(0x1F)
        iv_atk = (hab >> np.uint32(5)) & np.uint32(0x1F)
        iv_def = (hab >> np.uint32(10)) & np.uint32(0x1F)
        iv_spe = scd & np.uint32(0x1F)
        iv_spa = (scd >> np.uint32(5)) & np.uint32(0x1F)
        iv_spd = (scd >> np.uint32(10)) & np.uint32(0x1F)

        # ---- 段階的ステータス照合 (早期棄却) ----
        # HP (性格補正なし)
        hp = (2 * b_hp + iv_hp.astype(np.int32)) * level // 100 + level + 10
        ok = hp == o_hp
        if not ok.any():
            states = s1
            continue

        # 以降は ok でフィルタした部分配列で計算
        nids = nature_ids[ok]

        # Atk
        m_atk = nature_mult_arrays["Attack"][nids]
        raw_atk = (2 * b_atk + iv_atk[ok].astype(np.int32)) * level // 100 + 5
        atk = (raw_atk * m_atk).astype(np.int32)
        ok2 = atk == o_atk
        if not ok2.any():
            states = s1
            continue

        # Def
        nids2 = nids[ok2]
        m_def = nature_mult_arrays["Defense"][nids2]
        raw_def = (2 * b_def + iv_def[ok][ok2].astype(np.int32)) * level // 100 + 5
        def_ = (raw_def * m_def).astype(np.int32)
        ok3 = def_ == o_def
        if not ok3.any():
            states = s1
            continue

        # SpA
        nids3 = nids2[ok3]
        m_spa = nature_mult_arrays["SpecialAttack"][nids3]
        raw_spa = (2 * b_spa + iv_spa[ok][ok2][ok3].astype(np.int32)) * level // 100 + 5
        spa = (raw_spa * m_spa).astype(np.int32)
        ok4 = spa == o_spa
        if not ok4.any():
            states = s1
            continue

        # SpD
        nids4 = nids3[ok4]
        m_spd = nature_mult_arrays["SpecialDefense"][nids4]
        raw_spd = (2 * b_spd + iv_spd[ok][ok2][ok3][ok4].astype(np.int32)) * level // 100 + 5
        spd = (raw_spd * m_spd).astype(np.int32)
        ok5 = spd == o_spd
        if not ok5.any():
            states = s1
            continue

        # Spe
        nids5 = nids4[ok5]
        m_spe = nature_mult_arrays["Speed"][nids5]
        raw_spe = (2 * b_spe + iv_spe[ok][ok2][ok3][ok4][ok5].astype(np.int32)) * level // 100 + 5
        spe = (raw_spe * m_spe).astype(np.int32)
        ok6 = spe == o_spe
        if not ok6.any():
            states = s1
            continue

        # ---- ヒットした初期Seed を復元 ----
        all_idx = np.arange(len(ok))[ok]
        hit_idx = all_idx[ok2][ok3][ok4][ok5][ok6]
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
        return ("MULT", None)
