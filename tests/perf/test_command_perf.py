import statistics
import time

import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.command import DefaultCommand
from tests.support.fake_execution_context import make_fake_execution_context

OVERHEAD_THRESHOLD_S = 0.03


def _measure_overhead(cmd: DefaultCommand, keys, dur: float, wait: float, n: int) -> dict:
    expected_sleep = dur + wait
    overheads: list[float] = []
    totals: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        cmd.press(*keys, dur=dur, wait=wait)
        elapsed = time.perf_counter() - t0
        totals.append(elapsed)
        overheads.append(elapsed - expected_sleep)
    return {
        "overhead_avg": sum(overheads) / n,
        "overhead_median": sorted(overheads)[n // 2],
        "overhead_max": max(overheads),
        "total_avg": sum(totals) / n,
        "total_max": max(totals),
        "total_min": min(totals),
        "total_stdev": statistics.stdev(totals) if n > 1 else 0.0,
    }


def test_press_overhead(tmp_path):
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path))

    for _ in range(5):
        cmd.press(Button.A, dur=0.001, wait=0.001)

    stats = _measure_overhead(cmd, (Button.A,), dur=0.01, wait=0.01, n=100)

    assert stats["overhead_median"] < OVERHEAD_THRESHOLD_S


@pytest.mark.parametrize(
    "keys",
    [
        (Button.A,),
        (Button.B,),
        (Button.X, Button.Y),
        (Button.L, Button.R),
    ],
)
def test_press_overhead_mixed_input(tmp_path, keys):
    cmd = DefaultCommand(context=make_fake_execution_context(tmp_path))

    stats = _measure_overhead(cmd, keys, dur=0.01, wait=0.01, n=50)

    assert stats["overhead_median"] < OVERHEAD_THRESHOLD_S
