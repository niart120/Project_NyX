from __future__ import annotations

import numpy as np
import pytest

from nyxpy.framework.core.constants import Button, KeyboardOp, KeyCode
from nyxpy.framework.core.io.adapters import (
    CaptureFrameSourcePort,
    DummyFrameSourcePort,
    NoopNotificationAdapter,
    NotificationHandlerAdapter,
    NotificationHandlerPort,
    SerialControllerOutputPort,
)
from nyxpy.framework.core.io.ports import FrameNotReadyError


class SerialDevice:
    def __init__(self) -> None:
        self.sent = []

    def send(self, data) -> None:
        self.sent.append(data)


class Protocol:
    def __init__(self, *, keyboard_supported: bool = True) -> None:
        self.keyboard_supported = keyboard_supported

    def build_press_command(self, keys):
        return ("press", keys)

    def build_hold_command(self, keys):
        return ("hold", keys)

    def build_release_command(self, keys):
        return ("release", keys)

    def build_keyboard_command(self, text):
        if not self.keyboard_supported:
            raise NotImplementedError
        return ("keyboard", text)

    def build_keytype_command(self, key, op):
        return ("keytype", key, op)


class ThreeDSProtocol(Protocol):
    def build_touch_down_command(self, x, y):
        return ("touch_down", x, y)

    def build_touch_up_command(self):
        return ("touch_up",)

    def build_disable_sleep_command(self, enabled):
        return ("disable_sleep", enabled)


def test_controller_output_port_serializes_send_operations() -> None:
    serial = SerialDevice()
    port = SerialControllerOutputPort(serial, Protocol())

    port.press((Button.A,))
    port.hold((Button.B,))
    port.release()
    port.keyboard("AB")
    port.type_key(KeyCode("C"))

    assert serial.sent == [
        ("press", (Button.A,)),
        ("hold", (Button.B,)),
        ("release", ()),
        ("keyboard", "AB"),
        ("keytype", KeyCode(""), KeyboardOp.ALL_RELEASE),
        ("keytype", KeyCode("C"), KeyboardOp.PRESS),
        ("keytype", KeyCode("C"), KeyboardOp.RELEASE),
    ]


def test_serial_controller_touch_sends_3ds_frames() -> None:
    serial = SerialDevice()
    port = SerialControllerOutputPort(serial, ThreeDSProtocol())

    port.touch_down(320, 240)
    port.touch_up()

    assert serial.sent == [("touch_down", 320, 240), ("touch_up",)]


def test_serial_controller_disable_sleep_sends_3ds_command() -> None:
    serial = SerialDevice()
    port = SerialControllerOutputPort(serial, ThreeDSProtocol())

    port.disable_sleep(True)
    port.disable_sleep(False)

    assert serial.sent == [("disable_sleep", True), ("disable_sleep", False)]


def test_serial_controller_touch_unsupported_protocol_raises() -> None:
    port = SerialControllerOutputPort(SerialDevice(), Protocol())

    with pytest.raises(NotImplementedError, match="touch input"):
        port.touch_down(320, 240)
    with pytest.raises(NotImplementedError, match="sleep control"):
        port.disable_sleep(True)


def test_controller_output_port_keyboard_fallback_types_each_char() -> None:
    serial = SerialDevice()
    port = SerialControllerOutputPort(serial, Protocol(keyboard_supported=False))

    port.keyboard("AB")

    assert serial.sent == [
        ("keytype", KeyCode("A"), KeyboardOp.PRESS),
        ("keytype", KeyCode("A"), KeyboardOp.RELEASE),
        ("keytype", KeyCode("B"), KeyboardOp.PRESS),
        ("keytype", KeyCode("B"), KeyboardOp.RELEASE),
        ("keytype", KeyCode(""), KeyboardOp.ALL_RELEASE),
    ]


class CaptureDevice:
    def __init__(self, frames) -> None:
        self.frames = list(frames)
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def get_frame(self):
        if not self.frames:
            raise RuntimeError("not ready")
        return self.frames.pop(0)


def test_frame_source_await_ready_success_after_first_frame() -> None:
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    device = CaptureDevice([None, frame])
    port = CaptureFrameSourcePort(device)

    port.initialize()

    assert device.initialized is True
    assert port.await_ready(0.1) is True


def test_frame_source_await_ready_timeout() -> None:
    port = CaptureFrameSourcePort(CaptureDevice([]))

    assert port.await_ready(0.01) is False


def test_frame_source_latest_frame_returns_copy_and_reports_not_ready() -> None:
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    port = CaptureFrameSourcePort(CaptureDevice([frame]))

    latest = port.latest_frame()
    latest[0, 0, 0] = 0

    assert frame[0, 0, 0] == 1

    with pytest.raises(FrameNotReadyError):
        port.latest_frame()


def test_frame_source_try_latest_frame_returns_copy_and_skips_not_ready() -> None:
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    port = CaptureFrameSourcePort(CaptureDevice([frame, None]))

    latest = port.try_latest_frame()

    assert latest is not None
    latest[0, 0, 0] = 0
    assert frame[0, 0, 0] == 1
    assert port.try_latest_frame() is None


def test_frame_source_try_latest_frame_is_nonblocking() -> None:
    port = CaptureFrameSourcePort(CaptureDevice([np.ones((2, 2, 3), dtype=np.uint8)]))

    assert port._frame_lock.acquire(blocking=False)
    try:
        assert port.try_latest_frame() is None
    finally:
        port._frame_lock.release()


def test_dummy_frame_source_port_is_ready_after_initialize() -> None:
    port = DummyFrameSourcePort()

    assert port.await_ready(0) is False
    assert port.try_latest_frame() is None

    port.initialize()

    assert port.await_ready(0) is True
    assert port.latest_frame().shape == (720, 1280, 3)
    assert port.try_latest_frame() is not None


def test_notification_port_forwards_to_handler() -> None:
    calls = []

    class Handler:
        def publish(self, text, img=None) -> None:
            calls.append((text, img))

    image = np.zeros((1, 1, 3), dtype=np.uint8)
    NotificationHandlerAdapter(Handler()).publish("hello", image)

    assert calls == [("hello", image)]


def test_notification_handler_port_remains_backward_compatible() -> None:
    calls = []

    class Handler:
        def publish(self, text, img=None) -> None:
            calls.append((text, img))

    NotificationHandlerPort(Handler()).publish("hello")

    assert calls == [("hello", None)]


def test_noop_notification_adapter_ignores_publish() -> None:
    NoopNotificationAdapter().publish("hello")
