"""
DefaultCommand.press() パフォーマンステスト

テスト設計方針
-----------
press() の実行時間は「処理オーバーヘッド + sleep(dur) + sleep(wait)」で構成される。
sleep の精度は OS / Python バージョンに依存し、Python 3.11+ の Windows では
高精度タイマーにより ~1ms 精度で動作する。

本テストでは、処理オーバーヘッド (actual - (dur + wait)) が閾値内であることを検証する。
sleep 自体の精度テストではなく、press() に伴う非 sleep 処理コストを対象とする。

処理オーバーヘッドの主な内訳:
- check_interrupt デコレータ (press + wait ×2) → ~0.01ms
- log() 呼び出し ×4 (inspect.stack() + loguru) → 環境により 1–10ms
- protocol.build_{press,release}_command → ~0.01ms
- serial_device.send → ~0.01ms (ダミー)

NOTE: inspect.stack() のコストは pytest 環境下で増大する傾向がある。
閾値はこの影響を考慮した上で設定している。
"""

import statistics
import time

import pytest

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.constants.controller import Hat
from nyxpy.framework.core.constants.stick import LStick, RStick
from nyxpy.framework.core.hardware.protocol import (
    CH552SerialProtocol,
    PokeConSerialProtocol,
)
from nyxpy.framework.core.hardware.serial_comm import DummySerialComm
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.macro.command import DefaultCommand
from tests.unit.command.test_default_command import (
    MockCancellationToken,
    MockCaptureDevice,
    MockProtocol,
    MockResourceIO,
)


# ============================================================
# ヘルパー
# ============================================================


def _make_command(protocol) -> DefaultCommand:
    """テスト用 DefaultCommand を組み立てる。"""
    return DefaultCommand(
        serial_device=DummySerialComm("dummy"),
        capture_device=MockCaptureDevice(),
        resource_io=MockResourceIO(),
        protocol=protocol,
        ct=MockCancellationToken(),
        notification_handler=None,
    )


def _measure_overhead(
    cmd: DefaultCommand,
    keys,
    dur: float,
    wait: float,
    n: int,
) -> dict:
    """press() を n 回実行し、オーバーヘッド統計を返す。

    Returns:
        dict with keys: overhead_avg, overhead_median, overhead_max,
                        total_avg, total_max, total_min, total_stdev
    """
    expected_sleep = dur + wait
    overheads: list[float] = []
    totals: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        cmd.press(keys, dur=dur, wait=wait)
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


# ============================================================
# 1. 処理オーバーヘッド計測
# ============================================================

# 閾値: press() 1回あたりの処理オーバーヘッド (sleep を除いた部分)
# inspect.stack() ×4 + loguru + pytest 環境オーバーヘッドを含めて 15ms 以内を期待
OVERHEAD_THRESHOLD_S = 0.015


@pytest.mark.parametrize(
    "protocol_cls,proto_name",
    [
        (MockProtocol, "MockProtocol"),
        (CH552SerialProtocol, "CH552SerialProtocol"),
        (PokeConSerialProtocol, "PokeConSerialProtocol"),
    ],
)
def test_press_overhead(protocol_cls, proto_name):
    """press() の処理オーバーヘッド (sleep を除いた部分) が閾値内であること。

    dur/wait を小さく設定し、actual - expected_sleep でオーバーヘッドを分離する。
    """
    log_manager.set_level("INFO")
    cmd = _make_command(protocol_cls())

    # ウォームアップ (JIT 等の初回コストを排除)
    for _ in range(5):
        cmd.press(Button.A, dur=0.001, wait=0.001)

    stats = _measure_overhead(cmd, Button.A, dur=0.01, wait=0.01, n=100)

    print(
        f"[overhead] {proto_name}: "
        f"median={stats['overhead_median']*1000:.3f}ms, "
        f"avg={stats['overhead_avg']*1000:.3f}ms, "
        f"max={stats['overhead_max']*1000:.3f}ms"
    )
    assert stats["overhead_median"] < OVERHEAD_THRESHOLD_S, (
        f"処理オーバーヘッド中央値が {OVERHEAD_THRESHOLD_S*1000:.0f}ms を超過: "
        f"median={stats['overhead_median']*1000:.3f}ms"
    )


@pytest.mark.parametrize(
    "protocol_cls,proto_name",
    [
        (CH552SerialProtocol, "CH552SerialProtocol"),
        (PokeConSerialProtocol, "PokeConSerialProtocol"),
    ],
)
def test_press_overhead_mixed_input(protocol_cls, proto_name):
    """複雑な入力パターンでのオーバーヘッドが閾値内であること。"""
    log_manager.set_level("INFO")
    cmd = _make_command(protocol_cls())

    input_patterns = [
        Button.A,
        Button.B,
        [Button.X, Button.Y],
        Hat.UP,
        Hat.LEFT,
        [Button.L, Hat.DOWNRIGHT],
        LStick.UP,
        RStick.DOWNRIGHT,
        [Button.R, LStick.UP],
        [Hat.RIGHT, RStick.UP],
        [Button.ZL, Button.ZR, Hat.CENTER, RStick.DOWN],
        LStick.LEFT,
        LStick.RIGHT,
        [Button.PLUS, LStick.LEFT],
        [Button.MINUS, RStick.RIGHT],
    ]

    # ウォームアップ
    for p in input_patterns[:3]:
        cmd.press(p, dur=0.001, wait=0.001)

    expected_sleep = 0.02  # dur + wait
    overheads: list[float] = []
    n = 100
    for i in range(n):
        pattern = input_patterns[i % len(input_patterns)]
        t0 = time.perf_counter()
        cmd.press(pattern, dur=0.01, wait=0.01)
        elapsed = time.perf_counter() - t0
        overheads.append(elapsed - expected_sleep)

    median = sorted(overheads)[n // 2]
    avg = sum(overheads) / n
    print(
        f"[overhead-mixed] {proto_name}: "
        f"median={median*1000:.3f}ms, avg={avg*1000:.3f}ms, "
        f"max={max(overheads)*1000:.3f}ms"
    )
    assert median < OVERHEAD_THRESHOLD_S, (
        f"処理オーバーヘッド中央値が {OVERHEAD_THRESHOLD_S*1000:.0f}ms を超過: "
        f"median={median*1000:.3f}ms"
    )

