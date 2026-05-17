"""個体生成ロジック（第3世代 固定シンボル）

LCG32 から PID / IV を生成し、Pokemon データクラスとして保持する。
"""

from __future__ import annotations

from dataclasses import dataclass

from .lcg32 import LCG32


@dataclass(frozen=True)
class Pokemon:
    """LCG から生成された個体のデータ"""

    pid: int
    nature_id: int
    iv_hp: int
    iv_atk: int
    iv_def: int
    iv_spa: int
    iv_spd: int
    iv_spe: int

    def calc_stats(
        self,
        base_stats: tuple[int, int, int, int, int, int],
        level: int,
        nature_multipliers: dict[str, float],
    ) -> tuple[int, int, int, int, int, int]:
        """種族値・レベル・性格補正から実数値 (HP, Atk, Def, SpA, SpD, Spe) を算出する。

        努力値 (EV) は 0 を前提とする。
        """
        b_hp, b_atk, b_def, b_spa, b_spd, b_spe = base_stats

        hp = ((2 * b_hp + self.iv_hp) * level) // 100 + level + 10

        def _calc(base: int, iv: int, mult: float) -> int:
            return int(((2 * base + iv) * level // 100 + 5) * mult)

        atk = _calc(b_atk, self.iv_atk, nature_multipliers["Attack"])
        def_ = _calc(b_def, self.iv_def, nature_multipliers["Defense"])
        spa = _calc(b_spa, self.iv_spa, nature_multipliers["SpecialAttack"])
        spd = _calc(b_spd, self.iv_spd, nature_multipliers["SpecialDefense"])
        spe = _calc(b_spe, self.iv_spe, nature_multipliers["Speed"])

        return (hp, atk, def_, spa, spd, spe)


def generate_pokemon(lcg: LCG32) -> Pokemon:
    """現在の LCG 状態から個体を 1 体生成する。

    LCG を 4 step 消費する。

    生成順序:
        1. lid (PID 下位 16bit)
        2. hid (PID 上位 16bit)
        3. hab (HP / Attack / Defense の IV)
        4. scd (Speed / SpecialAttack / SpecialDefense の IV)
    """
    lid = lcg.get_rand()
    hid = lcg.get_rand()
    hab = lcg.get_rand()
    scd = lcg.get_rand()

    pid = lid | (hid << 16)

    return Pokemon(
        pid=pid,
        nature_id=pid % 25,
        iv_hp=hab & 0x1F,
        iv_atk=(hab >> 5) & 0x1F,
        iv_def=(hab >> 10) & 0x1F,
        iv_spe=scd & 0x1F,
        iv_spa=(scd >> 5) & 0x1F,
        iv_spd=(scd >> 10) & 0x1F,
    )
