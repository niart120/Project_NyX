from __future__ import annotations

import time
from threading import Lock

import cv2
import numpy as np

from nyxpy.framework.core.constants import KeyboardOp, KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.io.ports import (
    ControllerOutputPort,
    FrameNotReadyError,
    FrameReadError,
    FrameSourcePort,
    NotificationPort,
)
from nyxpy.framework.core.utils.helper import validate_keyboard_text


class SerialControllerOutputPort(ControllerOutputPort):
    def __init__(self, serial_device, protocol: SerialProtocolInterface) -> None:
        self.serial_device = serial_device
        self.protocol = protocol

    def press(self, keys: tuple[KeyType, ...]) -> None:
        self.serial_device.send(self.protocol.build_press_command(keys))

    def hold(self, keys: tuple[KeyType, ...]) -> None:
        self.serial_device.send(self.protocol.build_hold_command(keys))

    def release(self, keys: tuple[KeyType, ...] = ()) -> None:
        self.serial_device.send(self.protocol.build_release_command(keys))

    def keyboard(self, text: str) -> None:
        text = validate_keyboard_text(text)
        try:
            self.serial_device.send(self.protocol.build_keyboard_command(text))
        except (ValueError, NotImplementedError):
            for char in text:
                self.type_key(KeyCode(char))
        try:
            self.serial_device.send(
                self.protocol.build_keytype_command(KeyCode(""), KeyboardOp.ALL_RELEASE)
            )
        except NotImplementedError:
            pass

    def type_key(self, key: KeyCode | SpecialKeyCode) -> None:
        match key:
            case KeyCode():
                press_op = KeyboardOp.PRESS
                release_op = KeyboardOp.RELEASE
            case SpecialKeyCode():
                press_op = KeyboardOp.SPECIAL_PRESS
                release_op = KeyboardOp.SPECIAL_RELEASE
            case _:
                raise ValueError(f"Invalid key type: {type(key)}")
        self.serial_device.send(self.protocol.build_keytype_command(key, press_op))
        self.serial_device.send(self.protocol.build_keytype_command(key, release_op))

    def touch_down(self, x: int, y: int) -> None:
        builder = getattr(self.protocol, "build_touch_down_command", None)
        if builder is None:
            raise NotImplementedError("Current serial protocol does not support touch input.")
        self.serial_device.send(builder(x, y))

    def touch_up(self) -> None:
        builder = getattr(self.protocol, "build_touch_up_command", None)
        if builder is None:
            raise NotImplementedError("Current serial protocol does not support touch input.")
        self.serial_device.send(builder())

    def disable_sleep(self, enabled: bool = True) -> None:
        builder = getattr(self.protocol, "build_disable_sleep_command", None)
        if builder is None:
            raise NotImplementedError("Current serial protocol does not support sleep control.")
        self.serial_device.send(builder(enabled))

    def close(self) -> None:
        pass


class CaptureFrameSourcePort(FrameSourcePort):
    def __init__(self, capture_device) -> None:
        self.capture_device = capture_device
        self._frame_lock = Lock()

    def initialize(self) -> None:
        initialize = getattr(self.capture_device, "initialize", None)
        if initialize is not None:
            initialize()

    def await_ready(self, timeout: float) -> bool:
        if timeout is None or timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        deadline = time.monotonic() + timeout
        while True:
            if self._frame_lock.acquire(blocking=False):
                try:
                    try:
                        if self.capture_device.get_frame() is not None:
                            return True
                    except RuntimeError:
                        pass
                finally:
                    self._frame_lock.release()
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def latest_frame(self) -> cv2.typing.MatLike:
        if not self._frame_lock.acquire(timeout=0.1):
            raise FrameReadError("Frame source lock acquisition timed out.")
        try:
            frame = self.capture_device.get_frame()
        except RuntimeError as exc:
            raise FrameNotReadyError() from exc
        finally:
            self._frame_lock.release()
        return self._copy_ready_frame(frame)

    def try_latest_frame(self) -> cv2.typing.MatLike | None:
        if not self._frame_lock.acquire(blocking=False):
            return None
        try:
            try:
                frame = self.capture_device.get_frame()
            except RuntimeError:
                return None
        finally:
            self._frame_lock.release()
        if frame is None:
            return None
        return frame.copy()

    def _copy_ready_frame(self, frame) -> cv2.typing.MatLike:
        if frame is None:
            raise FrameNotReadyError()
        return frame.copy()

    def close(self) -> None:
        pass


class DummyFrameSourcePort(FrameSourcePort):
    def __init__(self, frame: cv2.typing.MatLike | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((720, 1280, 3), dtype=np.uint8)
        self.initialized = False
        self.closed = False

    def initialize(self) -> None:
        self.initialized = True

    def await_ready(self, timeout: float) -> bool:
        if timeout is None or timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        return self.initialized

    def latest_frame(self) -> cv2.typing.MatLike:
        if not self.initialized:
            raise FrameNotReadyError()
        return self._frame.copy()

    def try_latest_frame(self) -> cv2.typing.MatLike | None:
        if not self.initialized:
            return None
        return self._frame.copy()

    def close(self) -> None:
        self.closed = True


class NotificationHandlerAdapter(NotificationPort):
    def __init__(self, notification_handler) -> None:
        self.notification_handler = notification_handler

    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        self.notification_handler.publish(text, img)


class NoopNotificationAdapter(NotificationPort):
    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        pass


class NotificationHandlerPort(NotificationHandlerAdapter):
    """Backward-compatible alias for the notification port adapter."""
