import time
import threading
import pytest
import numpy as np
from nyxpy.framework.core.hardware.capture import AsyncCaptureDevice

@pytest.mark.realdevice
def test_continuous_frame_update():
    """
    長時間にわたり連続してフレームが取得されるかを確認するテスト。
    初期化後、複数回 get_latest_frame() で得られる内容が更新されていることを確認。
    実際のキャプチャデバイスを起動して、出力映像が変化するようにする必要があります。
    """
    device_index = 0  # 実際のデバイスに合わせる
    capture_device = AsyncCaptureDevice(device_index=device_index, interval=1/60)  # 60fps
    try:
        capture_device.initialize()
    except RuntimeError as e:
        pytest.skip(f"実デバイス未接続: {e}")
    time.sleep(0.5)  # 初期化後、少し待機してフレームが取得できるようにする
    initial_frame = capture_device.get_frame()
    time.sleep(0.5)  # 数秒待機してフレームが更新されるのを確認
    updated_frame = capture_device.get_frame()
    capture_device.release()
    
    # フレーム更新が確認できる場合、変更されているかを比較（内容が同一でも問題なければログ出力などで確認）
    assert updated_frame is not None, "更新されたフレームが None です。"
    assert not np.allclose(updated_frame, initial_frame), "フレームが更新されていない可能性があります。"

@pytest.mark.realdevice
def test_multithreaded_get_latest_frame():
    """
    複数スレッドから同時に get_latest_frame() を呼び出して、
    スレッドセーフに動作するかを検証するテスト。
    """
    device_index = 0
    capture_device = AsyncCaptureDevice(device_index=device_index, interval=0.1)
    try:
        capture_device.initialize()
    except RuntimeError as e:
        pytest.skip(f"実デバイス未接続: {e}")
    
    # 少し待ってから複数スレッドで取得
    time.sleep(1.0)
    frames = []
    def worker():
        frames.append(capture_device.get_frame())
    
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    capture_device.release()
    for frame in frames:
        assert frame is not None, "取得されたフレームが None です。"

@pytest.mark.realdevice
def test_release_idempotence():
    """
    release() を複数回呼んでも例外が発生せず、
    device の内部リソースが正しく解放されるかをテストする。
    """
    device_index = 0
    capture_device = AsyncCaptureDevice(device_index=device_index, interval=0.1)
    try:
        capture_device.initialize()
    except RuntimeError as e:
        pytest.skip(f"実デバイス未接続: {e}")

    time.sleep(1.0)
    capture_device.release()
    # 2回目の release() 呼び出しでも問題がないことを検証
    capture_device.release()
    # 内部リソースが解放され、cap が None になっていることを確認
    assert capture_device.cap is None, "cap が正しく解放されていません。"
