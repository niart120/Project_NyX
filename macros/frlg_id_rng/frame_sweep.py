"""
フレームインクリメント探索ジェネレータ

偶数パス → 奇数パスの順にフレーム値を列挙する。
Frame1 × Frame2 の2軸スイープおよび OPFrame の1軸スイープをサポートする。
"""

from __future__ import annotations

from typing import Iterator


def frame_sweep(
    min_val: float, max_val: float, step: float = 2.0
) -> Iterator[float]:
    """偶数パス → 奇数パスの順にフレーム値を列挙する。

    >>> list(frame_sweep(10, 16))
    [10.0, 12.0, 14.0, 16.0, 11.0, 13.0, 15.0]
    """
    # 偶数パス
    v = min_val
    while v <= max_val:
        yield v
        v += step

    # 奇数パス（範囲幅が 0 ならスキップ）
    if min_val < max_val:
        v = min_val + 1
        while v <= max_val:
            yield v
            v += step


def dual_frame_sweep(
    f1_min: float,
    f1_max: float,
    f2_min: float,
    f2_max: float,
) -> Iterator[tuple[float, float]]:
    """Frame1 × Frame2 の2軸スイープ。

    Frame2 の各値に対し Frame1 を全探索する（内側ループ = Frame1）。
    """
    for f2 in frame_sweep(f2_min, f2_max):
        for f1 in frame_sweep(f1_min, f1_max):
            yield f1, f2


def single_value_iterator(value: float) -> Iterator[float]:
    """固定値を1回だけ返す無限イテレータ。

    インクリメントモードが無効の場合に使用する。
    """
    while True:
        yield value
