import time
import pytest
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.constants import Button
from tests.unit.command.test_default_command import (
    MockSerialDevice,
    MockCaptureDevice,
    MockResourceIO,
    MockProtocol,
    MockCancellationToken,
)

def test_press_step_profile():
    """
    DefaultCommand.press() の各サブステップの実行時間を詳細計測
    - build_press_command, serial_device.send, wait, build_release_command, ...
    """
    serial_device = MockSerialDevice()
    capture_device = MockCaptureDevice()
    resource_io = MockResourceIO()
    protocol = MockProtocol()
    ct = MockCancellationToken()
    cmd = DefaultCommand(
        serial_device=serial_device,
        capture_device=capture_device,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct,
        notification_handler=None,
    )
    keys = (Button.A,)
    dur = 0.01
    wait = 0.01
    t0 = time.perf_counter()
    press_data = protocol.build_press_command(keys)
    t1 = time.perf_counter()
    serial_device.send(press_data)
    t2 = time.perf_counter()
    time.sleep(dur)
    t3 = time.perf_counter()
    release_data = protocol.build_release_command(keys)
    t4 = time.perf_counter()
    serial_device.send(release_data)
    t5 = time.perf_counter()
    time.sleep(wait)
    t6 = time.perf_counter()
    print(f"[step profile] build_press: {(t1-t0)*1000:.3f}ms, send_press: {(t2-t1)*1000:.3f}ms, wait_dur: {(t3-t2)*1000:.3f}ms, build_release: {(t4-t3)*1000:.3f}ms, send_release: {(t5-t4)*1000:.3f}ms, wait_post: {(t6-t5)*1000:.3f}ms")
    # 合計も出力
    print(f"[step profile] total: {(t6-t0)*1000:.3f}ms")
