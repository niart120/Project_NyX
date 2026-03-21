"""FRLG OP スキップ〜回想スキップ共通ヘルパー。

OP スキップ → つづきからはじめる → 回想スキップの操作シーケンスを提供する。
"""

from __future__ import annotations

from macros.shared.timer import start_timer
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.command import Command


def skip_opening_and_continue(cmd: Command) -> float:
    """OP スキップ → つづきからはじめる → 回想スキップを実行し、timer1 の開始時刻を返す。

    frame1 タイマー消化完了直後に呼び出すこと。
    関数の入口で timer1 を開始し、OP スキップ〜回想スキップまでの操作を
    timer1 の中に吸収させる。

    Returns:
        start_timer() による timer1 開始時刻
    """
    t1 = start_timer()
    cmd.press(Button.A, dur=3.50, wait=1.00)  # OP スキップ
    cmd.press(Button.A, dur=0.20, wait=0.30)  # つづきからはじめる
    cmd.press(Button.B, dur=1.00, wait=1.80)  # 回想スキップ
    return t1
