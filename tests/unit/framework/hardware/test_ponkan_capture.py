from __future__ import annotations

import sys
import time
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from nyxpy.framework.core.hardware.camera_capture import (
    CaptureDeviceNotReady,
    CaptureDeviceReadFailed,
)
from nyxpy.framework.core.hardware.capture_source import PonkanCaptureSourceConfig
from nyxpy.framework.core.hardware.ponkan_capture import (
    PonkanCaptureDevice,
    _open_ponkan_capture,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


class FakeReader:
    def __init__(self, *frames, error: Exception | None = None) -> None:
        self.frames = list(frames)
        self.error = error
        self.read_calls = []
        self.close_calls = 0

    def read(self, *, output=None, colorspace=None, timeout=None):
        self.read_calls.append(
            {
                "output": output,
                "colorspace": colorspace,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        if not self.frames:
            time.sleep(0.001)
            return None
        return self.frames.pop(0)

    def stats(self):
        return {}

    def close(self) -> None:
        self.close_calls += 1


def _wait_until(assertion, *, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: AssertionError | None = None
    while time.monotonic() < deadline:
        try:
            assertion()
            return
        except AssertionError as exc:
            last_error = exc
            time.sleep(0.01)
    if last_error is not None:
        raise last_error


def test_ponkan_capture_device_caches_bgr_frame_copy() -> None:
    frame = np.ones((480, 400, 3), dtype=np.uint8)
    reader = FakeReader(frame)
    device = PonkanCaptureDevice(
        PonkanCaptureSourceConfig(read_timeout=0.25),
        opener=lambda _config: reader,
    )

    device.initialize()

    def assert_frame_ready() -> None:
        latest = device.get_frame()
        latest[0, 0, 0] = 0
        assert frame[0, 0, 0] == 1

    _wait_until(assert_frame_ready)
    device.release()

    assert reader.read_calls[0] == {
        "output": "both_vertical",
        "colorspace": "BGR",
        "timeout": 0.25,
    }


def test_ponkan_capture_device_raises_not_ready_before_first_frame() -> None:
    reader = FakeReader()
    device = PonkanCaptureDevice(PonkanCaptureSourceConfig(), opener=lambda _config: reader)

    device.initialize()

    with pytest.raises(CaptureDeviceNotReady):
        device.get_frame()

    device.release()


def test_ponkan_capture_device_close_is_idempotent() -> None:
    reader = FakeReader()
    device = PonkanCaptureDevice(PonkanCaptureSourceConfig(), opener=lambda _config: reader)

    device.initialize()
    device.release()
    device.release()

    assert reader.close_calls == 1


def test_ponkan_capture_device_reports_reader_failure() -> None:
    reader = FakeReader(error=RuntimeError("usb read failed"))
    device = PonkanCaptureDevice(PonkanCaptureSourceConfig(), opener=lambda _config: reader)

    device.initialize()

    def assert_read_failed() -> None:
        with pytest.raises(CaptureDeviceReadFailed):
            device.get_frame()

    _wait_until(assert_read_failed)
    device.release()


def test_ponkan_capture_missing_dependency_is_configuration_error(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "ponkan", None)

    with pytest.raises(ConfigurationError) as exc_info:
        _open_ponkan_capture(PonkanCaptureSourceConfig())

    assert exc_info.value.code == "NYX_PONKAN_CAPTURE_DEPENDENCY_MISSING"
    assert exc_info.value.details["extra"] == "ponkan"


def test_ponkan_capture_dependency_unavailable_is_configuration_error(monkeypatch) -> None:
    class CaptureError(Exception):
        pass

    class DependencyUnavailableError(CaptureError):
        pass

    error = DependencyUnavailableError("missing pyd3xx")
    _install_fake_ponkan(monkeypatch, CaptureError, DependencyUnavailableError, error)

    with pytest.raises(ConfigurationError) as exc_info:
        _open_ponkan_capture(PonkanCaptureSourceConfig(ponkan_backend="d3xx"))

    assert exc_info.value.code == "NYX_PONKAN_CAPTURE_DEPENDENCY_UNAVAILABLE"
    assert exc_info.value.details["backend"] == "d3xx"


def test_ponkan_open_capture_uses_upstream_default_device_selection(monkeypatch) -> None:
    class CaptureError(Exception):
        pass

    class DependencyUnavailableError(CaptureError):
        pass

    calls = _install_fake_ponkan(monkeypatch, CaptureError, DependencyUnavailableError)

    reader = _open_ponkan_capture(
        PonkanCaptureSourceConfig(
            ponkan_backend="d3xx-native",
            raw_slots=3,
            output_queue_size=4,
            drop_policy="block",
            poll_interval=0.01,
            read_timeout=None,
            collect_timing=True,
        )
    )

    assert isinstance(reader, FakeReader)
    assert calls["open_args"] == ()
    config = calls["open_kwargs"]["config"]
    assert config.backend == "d3xx-native"
    assert config.raw_slots == 3
    assert config.output_queue_size == 4
    assert config.drop_policy == "block"
    assert config.poll_interval == 0.01
    assert config.read_timeout is None
    assert config.collect_timing is True


def _install_fake_ponkan(
    monkeypatch,
    capture_error_type: type[Exception],
    dependency_unavailable_type: type[Exception],
    open_error: Exception | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {}

    class CaptureConfig:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    def open_capture(*args, **kwargs):
        calls["open_args"] = args
        calls["open_kwargs"] = kwargs
        if open_error is not None:
            raise open_error
        return FakeReader()

    ponkan = ModuleType("ponkan")
    ponkan.CaptureConfig = CaptureConfig
    ponkan.CaptureOutput = SimpleNamespace(BOTH_VERTICAL="both_vertical")
    ponkan.open_capture = open_capture

    errors = ModuleType("ponkan.errors")
    errors.CaptureError = capture_error_type
    errors.DependencyUnavailableError = dependency_unavailable_type

    monkeypatch.setitem(sys.modules, "ponkan", ponkan)
    monkeypatch.setitem(sys.modules, "ponkan.errors", errors)
    return calls
