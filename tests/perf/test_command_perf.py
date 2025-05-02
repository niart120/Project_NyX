import time
import statistics
import pytest
from nyxpy.framework.core.hardware.protocol import CH552SerialProtocol, PokeConSerialProtocol
from nyxpy.framework.core.logger.log_manager import log_manager
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.constants import Button

# 既存Mockをunitテストから流用
from tests.unit.command.test_default_command import (
    MockSerialDevice,
    MockCaptureDevice,
    MockResourceIO,
    MockProtocol,
    MockCancellationToken,
)

@pytest.mark.parametrize("protocol_cls,proto_name", [
    (MockProtocol, "MockProtocol"),
    (CH552SerialProtocol, "CH552SerialProtocol"),
    (PokeConSerialProtocol, "PokeConSerialProtocol")
])
def test_press_performance(protocol_cls, proto_name):
    """
    DefaultCommand.press() のパフォーマンステスト
    - 各プロトコルごとに100回pressを実行し、実行時間の分布を計測
    - wait/sleep等も含めたコマンド全体の遅延を測定
    """

    log_manager.set_level("INFO")  # INFOレベルに設定
    serial_device = MockSerialDevice()
    capture_device = MockCaptureDevice()
    resource_io = MockResourceIO()
    protocol = protocol_cls()
    ct = MockCancellationToken()
    cmd = DefaultCommand(
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct,
        notification_handler=None,
    )
    N = 100
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        cmd.press(Button.A, dur=0.01, wait=0.01)  # 実行時間を短縮
        t1 = time.perf_counter()
        times.append(t1 - t0)
    avg = sum(times) / N
    stdev = statistics.stdev(times) if N > 1 else 0
    print(f"[perf] {proto_name} press: avg={avg*1000:.3f}ms, max={max(times)*1000:.3f}ms, min={min(times)*1000:.3f}ms, stdev={stdev*1000:.3f}ms")
    # 目安として1回25ms未満を期待（環境依存なのでassertは緩め）
    assert avg < 0.025, f"avg={avg*1000:.3f}ms, max={max(times)*1000:.3f}ms, min={min(times)*1000:.3f}ms, stdev={stdev*1000:.3f}ms"
    # 1回あたりの最大値が50msを超えた場合は警告を出す
    if max(times) > 0.05:
        print(f"[perf] WARNING: {proto_name} press max time exceeded 50ms: {max(times)*1000:.3f}ms")
