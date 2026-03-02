"""GBA ポケモン用 32bit 線形合同法 (LCG) 乱数生成器

FRLG（第3世代）の乱数生成器を Python で再現する。
PokemonPRNG.LCG32.StandardLCG と同等の機能を提供する。
"""

from __future__ import annotations


class LCG32:
    """GBA ポケモン用 32bit 線形合同法 乱数生成器"""

    A: int = 0x41C64E6D
    C: int = 0x00006073
    MASK: int = 0xFFFFFFFF

    # 逆方向用定数 (A_INV ≡ A^(-1) mod 2^32, C_INV ≡ -C × A^(-1) mod 2^32)
    A_INV: int = 0xEEB9EB65
    C_INV: int = 0x0A3561A1

    def __init__(self, seed: int) -> None:
        self._seed = seed & self.MASK

    @property
    def seed(self) -> int:
        """現在の内部 seed 値を返す。"""
        return self._seed

    def advance(self, n: int = 1) -> None:
        """seed を n step 前進させる。"""
        for _ in range(n):
            self._seed = (self.A * self._seed + self.C) & self.MASK

    def back(self, n: int = 1) -> None:
        """seed を n step 後退させる。"""
        for _ in range(n):
            self._seed = (self.A_INV * self._seed + self.C_INV) & self.MASK

    def get_rand(self) -> int:
        """Advance(1) してから上位 16bit を返す。"""
        self.advance()
        return (self._seed >> 16) & 0xFFFF
