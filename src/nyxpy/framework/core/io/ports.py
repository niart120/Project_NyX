from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.macro.exceptions import DeviceError


class FrameNotReadyError(DeviceError):
    def __init__(self, message: str = "Frame source is not ready.") -> None:
        super().__init__(
            message,
            code="NYX_FRAME_NOT_READY",
            component="FrameSourcePort",
        )


class FrameReadError(DeviceError):
    def __init__(self, message: str = "Frame source read failed.") -> None:
        super().__init__(
            message,
            code="NYX_FRAME_READ_FAILED",
            component="FrameSourcePort",
        )


class ControllerOutputPort(ABC):
    @abstractmethod
    def press(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def hold(self, keys: tuple[KeyType, ...]) -> None: ...

    @abstractmethod
    def release(self, keys: tuple[KeyType, ...] = ()) -> None: ...

    @abstractmethod
    def keyboard(self, text: str) -> None: ...

    @abstractmethod
    def type_key(self, key: KeyCode | SpecialKeyCode) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


@runtime_checkable
class TouchInputCapability(Protocol):
    def touch_down(self, x: int, y: int) -> None: ...

    def touch_up(self) -> None: ...


@runtime_checkable
class SleepControlCapability(Protocol):
    def disable_sleep(self, enabled: bool = True) -> None: ...


class FrameSourcePort(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def await_ready(self, timeout: float) -> bool: ...

    @abstractmethod
    def latest_frame(self) -> cv2.typing.MatLike: ...

    @abstractmethod
    def try_latest_frame(self) -> cv2.typing.MatLike | None: ...

    @abstractmethod
    def close(self) -> None: ...


class NotificationPort(ABC):
    @abstractmethod
    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None: ...
