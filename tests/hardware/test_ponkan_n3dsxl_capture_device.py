"""ponkan capture source の実機 smoke test。"""

from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

from nyxpy.framework.core.hardware.camera_capture import CaptureDeviceNotReady
from nyxpy.framework.core.hardware.capture_source import PonkanCaptureSourceConfig
from nyxpy.framework.core.hardware.ponkan_capture import PonkanCaptureDevice

pytestmark = [
    pytest.mark.realdevice,
    pytest.mark.skipif(
        os.environ.get("NYX_REALDEVICE") != "1" or os.environ.get("NYX_N3DSXL_CAPTURE") != "1",
        reason="set NYX_REALDEVICE=1 and NYX_N3DSXL_CAPTURE=1 to run n3dsxl capture tests",
    ),
]


def test_ponkan_n3dsxl_capture_device_realdevice(tmp_path) -> None:
    device = PonkanCaptureDevice(
        PonkanCaptureSourceConfig(
            ponkan_backend="auto",
            read_timeout=1.0,
            collect_timing=True,
        )
    )

    device.initialize()
    try:
        frame = _wait_for_frame(device, timeout=5.0)
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3
        assert frame.shape[2] == 3
        assert frame.dtype == np.uint8
        _write_stats_snapshot(device, tmp_path / "ponkan_capture_stats.json")
    finally:
        device.release()


def _wait_for_frame(device: PonkanCaptureDevice, *, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return device.get_frame()
        except CaptureDeviceNotReady:
            time.sleep(0.05)
    pytest.fail("ponkan capture did not produce a frame within timeout")


def _write_stats_snapshot(device: PonkanCaptureDevice, path) -> None:
    reader = getattr(device, "_reader", None)
    if reader is None:
        return
    stats = reader.stats()
    if hasattr(stats, "snapshot"):
        value = stats.snapshot()
    elif hasattr(stats, "to_dict"):
        value = stats.to_dict()
    else:
        value = repr(stats)
    path.write_text(json.dumps(_jsonable(value), ensure_ascii=False, indent=2), encoding="utf-8")


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return repr(value)
