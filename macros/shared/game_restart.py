"""ゲーム再起動共通ヘルパー。

HOME メニュー経由でゲームを終了→再起動する操作を提供する。
"""

from __future__ import annotations

from macros.shared.timer import start_timer
from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.command import Command


def restart_game(cmd: Command) -> float:
    """HOME メニュー経由でゲームを終了→再起動し、timer0 の開始時刻を返す。

    Returns:
        start_timer() による timer0 開始時刻
    """
    cmd.press(Button.HOME, dur=0.15, wait=1.00)
    cmd.press(Button.X, dur=0.20, wait=0.60)
    cmd.press(Button.A, dur=0.20, wait=1.20)
    cmd.press(Button.A, dur=0.20, wait=0.80)
    t0 = start_timer()
    cmd.press(Button.A, dur=0.20)
    return t0
