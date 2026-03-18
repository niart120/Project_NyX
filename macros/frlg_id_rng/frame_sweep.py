"""
フレームインクリメント探索ジェネレータ

min_val から max_val まで step ずつフレーム値を列挙する。
Frame1 × Frame2 の2軸スイープおよび OPFrame の1軸スイープをサポートする。
"""

from __future__ import annotations

from collections.abc import Iterator


def frame_sweep(
    min_val: float, max_val: float, step: float = 1.0
) -> Iterator[float]:
    """min_val から max_val まで step ずつフレーム値を列挙する。

    >>> list(frame_sweep(10, 13))
    [10.0, 11.0, 12.0, 13.0]
    """
    v = min_val
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

    Frame1 の各値に対し Frame2 を全探索する（内側ループ = Frame2）。
    """
    for f1 in frame_sweep(f1_min, f1_max):
        for f2 in frame_sweep(f2_min, f2_max):
            yield f1, f2


def single_value_iterator(value: float) -> Iterator[float]:
    """固定値を1回だけ返す無限イテレータ。

    インクリメントモードが無効の場合に使用する。
    """
    while True:
        yield value
