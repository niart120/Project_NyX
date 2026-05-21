"""Runtime が依存する入出力 port interface。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import cv2

from nyxpy.framework.core.constants import KeyCode, KeyType, SpecialKeyCode
from nyxpy.framework.core.macro.exceptions import DeviceError


class FrameNotReadyError(DeviceError):
    """Frame source がまだ読み出し可能な frame を持たない場合の例外。"""

    def __init__(self, message: str = "Frame source is not ready.") -> None:
        """Frame 未準備を示す framework error として初期化します。"""
        super().__init__(
            message,
            code="NYX_FRAME_NOT_READY",
            component="FrameSourcePort",
        )


class FrameReadError(DeviceError):
    """Frame source からの frame 読み出しに失敗した場合の例外。"""

    def __init__(self, message: str = "Frame source read failed.") -> None:
        """Frame 読み出し失敗を示す framework error として初期化します。"""
        super().__init__(
            message,
            code="NYX_FRAME_READ_FAILED",
            component="FrameSourcePort",
        )


class ControllerOutputPort(ABC):
    """Runtime が controller 入力を送るための出力 port。"""

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

    @property
    def supports_touch(self) -> bool:
        return False

    def touch_down(self, x: int, y: int) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")

    def touch_up(self) -> None:
        raise NotImplementedError("Current controller output does not support touch input.")

    def disable_sleep(self, enabled: bool = True) -> None:
        raise NotImplementedError("Current controller output does not support sleep control.")


class FrameSourcePort(ABC):
    """Runtime が最新 frame を取得するための入力 port。"""

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
    """Runtime が外部通知を送るための port。"""

    @abstractmethod
    def publish(self, text: str, img: cv2.typing.MatLike | None = None) -> None: ...
