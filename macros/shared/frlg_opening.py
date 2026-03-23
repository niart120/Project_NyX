"""FRLG OP スキップ〜回想スキップ共通ヘルパー。

OP スキップ → frame2 待機 → つづきからはじめる → 回想スキップの操作シーケンスを提供する。
"""

from __future__ import annotations

from macros.shared.timer import consume_timer, start_timer
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.command import Command

# 初期 Seed 決定から「つづきからはじめる」までの待機フレーム数 (5.000s × 60fps)
# その時点の advance を安定させるためのタイミング制御
_FRAME2: float = 300.0
_FPS: float = 60.0


def skip_opening_and_continue(cmd: Command) -> float:
    """OP スキップ → frame2 待機 → つづきからはじめる → 回想スキップを実行し、timer1 の開始時刻を返す。

    frame1 タイマー消化完了直後に呼び出すこと。
    関数の入口で timer1 を開始し、OP スキップ後に frame2 タイマーで
    初期 Seed 決定から 5.000s 経過するまで待機し、「つづきからはじめる」を選択する。

    Returns:
        start_timer() による timer1 開始時刻
    """
    t1 = start_timer()
    cmd.press(Button.A, dur=3.50, wait=1.00)  # OP スキップ
    consume_timer(cmd, t1, _FRAME2, _FPS)     # frame2 タイマー消化
    cmd.press(Button.A, dur=0.20, wait=0.30)  # つづきからはじめる
    cmd.press(Button.B, dur=1.00, wait=1.80)  # 回想スキップ
    return t1
