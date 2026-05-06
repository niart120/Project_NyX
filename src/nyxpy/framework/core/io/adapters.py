from __future__ import annotations

import time

import cv2

from nyxpy.framework.core.constants import KeyboardOp, KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface
from nyxpy.framework.core.io.ports import (
    ControllerOutputPort,
    FrameNotReadyError,
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

    def close(self) -> None:
        pass


class CaptureFrameSourcePort(FrameSourcePort):
    def __init__(self, capture_device) -> None:
        self.capture_device = capture_device

    def initialize(self) -> None:
        initialize = getattr(self.capture_device, "initialize", None)
        if initialize is not None:
            initialize()

    def await_ready(self, timeout: float) -> bool:
        if timeout is None or timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        deadline = time.monotonic() + timeout
        while True:
            try:
                if self.capture_device.get_frame() is not None:
                    return True
            except RuntimeError:
                pass
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def latest_frame(self) -> cv2.typing.MatLike:
        try:
            frame = self.capture_device.get_frame()
        except RuntimeError as exc:
            raise FrameNotReadyError() from exc
        if frame is None:
            raise FrameNotReadyError()
        return frame.copy()

    def close(self) -> None:
        pass


class NotificationHandlerPort(NotificationPort):
    def __init__(self, notification_handler) -> None:
        self.notification_handler = notification_handler

    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None:
        if self.notification_handler is not None:
            self.notification_handler.publish(text, img)
