"""フレーム精度タイマーヘルパー。

perf_counter ベースの高精度タイマーで、フレーム指定の待機を実現する。
"""

from __future__ import annotations

import time

from nyxpy.framework.core.macro.command import Command


def start_timer() -> float:
    """高精度タイマーの開始時刻を返す。"""
    return time.perf_counter()


def consume_timer(
    cmd: Command,
    start_time: float,
    total_frames: float,
    fps: float,
) -> None:
    """開始時刻からの経過時間を差し引き、残りフレーム分だけ待機する。

    超過が 0.5 秒以上の場合は WARNING ログを出力する。

    :param cmd: コマンドインターフェース（wait / log のみ使用）
    :param start_time: start_timer() で取得した開始時刻
    :param total_frames: 待機すべき合計フレーム数
    :param fps: フレームレート
    """
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
    elif remaining < -0.5:
        overrun_ms = -remaining * 1000
        cmd.log(
            f"タイマー超過: {total_frames:.0f}F/{fps}fps={target_seconds:.3f}s に対し "
            f"経過 {elapsed:.3f}s（超過 {overrun_ms:.1f}ms）",
            level="WARNING",
        )
